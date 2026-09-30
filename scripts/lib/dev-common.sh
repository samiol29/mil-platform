#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Shared helpers for scripts/dev-up.sh, scripts/dev-down.sh, scripts/status.sh
#
# Sourced, never executed directly. Written for portability against macOS's
# stock /bin/bash (3.2 — no associative arrays, no `mapfile`), since that is
# what `#!/usr/bin/env bash` resolves to on an unmodified Mac.
#
# Process/registry model:
#   Every long-running dev process this toolkit manages (API, one process
#   per worker, frontend) gets one PID file under $MIL_DEV_PID_DIR and one
#   log file under $MIL_DEV_LOG_DIR, both named after its registry key
#   (e.g. "api", "worker-ocr", "frontend"). dev-up.sh writes them,
#   dev-down.sh removes them, status.sh only ever reads them — none of the
#   three scripts hardcodes a PID anywhere.
# ---------------------------------------------------------------------------

# Guard against being executed directly instead of sourced.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "dev-common.sh is a library — source it from dev-up.sh/dev-down.sh/status.sh, don't run it directly." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Resolve the repository root relative to this file, not the caller's CWD,
# so every script works regardless of where it's invoked from.
MIL_DEV_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIL_REPO_ROOT="$(cd "${MIL_DEV_LIB_DIR}/../.." && pwd)"
MIL_FRONTEND_DIR="${MIL_REPO_ROOT}/frontend"
MIL_VENV_DIR="${MIL_REPO_ROOT}/.venv"
MIL_DEV_PID_DIR="${MIL_REPO_ROOT}/.dev/pids"
MIL_DEV_LOG_DIR="${MIL_REPO_ROOT}/logs/dev"

# Hard disk-safety limits for dev logs. Every managed process's output goes
# through scripts/lib/rotate_log.py, so one process can use at most
# MAX_MB * (BACKUPS + 1) on disk (default 10 MB * 4 = 40 MB; 7 processes =
# 280 MB worst case) however much it writes. dev-up.sh also refuses to start
# when free disk is below MIN_FREE_MB. Override via the environment if needed.
MIL_DEV_LOG_MAX_MB="${MIL_DEV_LOG_MAX_MB:-10}"
MIL_DEV_LOG_BACKUPS="${MIL_DEV_LOG_BACKUPS:-3}"
MIL_DEV_MIN_FREE_MB="${MIL_DEV_MIN_FREE_MB:-5120}"

mkdir -p "${MIL_DEV_PID_DIR}" "${MIL_DEV_LOG_DIR}"

# ---------------------------------------------------------------------------
# Colour output — disabled automatically when not attached to a terminal
# (CI logs, redirected output) or when NO_COLOR is set (https://no-color.org).
# ---------------------------------------------------------------------------

if [[ -t 1 ]] && [[ -z "${NO_COLOR:-}" ]]; then
  C_RESET=$'\033[0m'
  C_BOLD=$'\033[1m'
  C_RED=$'\033[31m'
  C_GREEN=$'\033[32m'
  C_YELLOW=$'\033[33m'
  C_BLUE=$'\033[34m'
  C_DIM=$'\033[2m'
else
  C_RESET=""; C_BOLD=""; C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_DIM=""
fi

log_info()  { printf '%s\n' "${C_BLUE}→${C_RESET} $*"; }
log_ok()    { printf '%s\n' "${C_GREEN}✓${C_RESET} $*"; }
log_warn()  { printf '%s\n' "${C_YELLOW}⚠${C_RESET} $*"; }
log_err()   { printf '%s\n' "${C_RED}✗${C_RESET} $*" >&2; }
log_step()  { printf '\n%s\n' "${C_BOLD}$*${C_RESET}"; }

# ---------------------------------------------------------------------------
# Registry of managed processes (parallel arrays — bash 3.2 has no
# associative arrays). Index i across all three arrays describes one
# managed process. This is the single source of truth every script reads
# from, so adding a sixth worker later is a one-line change in one place.
# ---------------------------------------------------------------------------

MIL_PROC_KEYS=(api worker-ocr worker-extraction worker-finding worker-policy worker-review frontend)
MIL_PROC_LABELS=("Backend API" "OCR Worker" "Extraction Worker" "Finding Worker" "Policy Worker" "Review Worker" "Frontend")

# ---------------------------------------------------------------------------
# PID file helpers
# ---------------------------------------------------------------------------

pid_file_for() { printf '%s/%s.pid' "${MIL_DEV_PID_DIR}" "$1"; }
log_file_for() { printf '%s/%s.log' "${MIL_DEV_LOG_DIR}" "$1"; }

# pid_alive PID — true if PID refers to a live process.
pid_alive() {
  local pid="$1"
  [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null
}

# running_pid KEY — echoes the live PID for KEY's registered process, or
# nothing if its PID file is absent or stale (process no longer alive).
# A stale PID file is left in place for the caller to decide what to do
# with (status.sh reports it; dev-up.sh removes it before respawning).
running_pid() {
  local key="$1"
  local file
  file="$(pid_file_for "${key}")"
  [[ -f "${file}" ]] || return 0
  local pid
  pid="$(cat "${file}" 2>/dev/null || true)"
  if pid_alive "${pid}"; then
    printf '%s\n' "${pid}"
  fi
}

# is_stale_pid_file KEY — true if a PID file exists but its process is dead.
is_stale_pid_file() {
  local key="$1"
  local file
  file="$(pid_file_for "${key}")"
  [[ -f "${file}" ]] || return 1
  local pid
  pid="$(cat "${file}" 2>/dev/null || true)"
  [[ -n "${pid}" ]] && ! pid_alive "${pid}"
}

# free_disk_mb DIR — free space, in MB, on the filesystem holding DIR.
free_disk_mb() {
  df -Pk "$1" | awk 'NR==2 {print int($4 / 1024)}'
}

# start_managed KEY LABEL WORKDIR CMD... — starts CMD in the background from
# WORKDIR, detached from this shell's job control (so it survives the
# launcher script exiting) with stdout+stderr sent through rotate_log.py into
# a size-capped, rotating log file, and records CMD's PID. No-op (with a
# message) if KEY is already running.
start_managed() {
  local key="$1" label="$2" workdir="$3"
  shift 3
  local existing
  existing="$(running_pid "${key}")"
  if [[ -n "${existing}" ]]; then
    log_warn "${label} already running (pid ${existing}) — not starting a duplicate."
    return 0
  fi
  is_stale_pid_file "${key}" && rm -f "$(pid_file_for "${key}")"

  local log_file
  log_file="$(log_file_for "${key}")"
  : > "${log_file}"
  # Stale rotated backups belong to a previous session (the live file was just
  # truncated, same as before) — drop them so retained logs stay bounded.
  rm -f "${log_file}".[0-9]*

  (
    cd "${workdir}"
    # setsid (Linux) puts the process in its own session so dev-down.sh's
    # SIGTERM doesn't race with the launching shell's own exit; macOS has no
    # setsid, so fall back to plain nohup/disown there — still fully
    # detached from THIS script's controlling terminal via `disown`.
    # Output goes to a rotating, size-capped sink via process substitution
    # (not a pipeline), so `$!` below is still CMD's own PID and the sink
    # exits by itself once CMD closes its output.
    if command -v setsid >/dev/null 2>&1; then
      exec setsid "$@" > >(python3 "${MIL_DEV_LIB_DIR}/rotate_log.py" "${log_file}" "${MIL_DEV_LOG_MAX_MB}" "${MIL_DEV_LOG_BACKUPS}") 2>&1
    else
      exec "$@" > >(python3 "${MIL_DEV_LIB_DIR}/rotate_log.py" "${log_file}" "${MIL_DEV_LOG_MAX_MB}" "${MIL_DEV_LOG_BACKUPS}") 2>&1
    fi
  ) &
  local pid=$!
  disown "${pid}" 2>/dev/null || true
  echo "${pid}" > "$(pid_file_for "${key}")"
  log_ok "${label} started (pid ${pid}), logging to ${log_file#"${MIL_REPO_ROOT}"/}"
}

# stop_managed KEY LABEL — SIGTERM then, after a grace period, SIGKILL.
# Always removes the PID file, even if the process was already gone.
stop_managed() {
  local key="$1" label="$2"
  local file
  file="$(pid_file_for "${key}")"
  if [[ ! -f "${file}" ]]; then
    log_warn "${label}: not running (no PID file)."
    return 0
  fi
  local pid
  pid="$(cat "${file}" 2>/dev/null || true)"
  if ! pid_alive "${pid}"; then
    log_warn "${label}: PID file present but process already gone — cleaning up."
    rm -f "${file}"
    return 0
  fi

  kill -TERM "${pid}" 2>/dev/null || true
  local waited=0
  while pid_alive "${pid}" && (( waited < 10 )); do
    sleep 0.5
    waited=$((waited + 1))
  done
  if pid_alive "${pid}"; then
    log_warn "${label}: did not stop after SIGTERM, sending SIGKILL."
    kill -KILL "${pid}" 2>/dev/null || true
    sleep 0.5
  fi
  rm -f "${file}"
  log_ok "${label} stopped."
}

# ---------------------------------------------------------------------------
# Network readiness helpers — poll a real condition instead of sleeping a
# fixed duration. Every wait_for_* takes a timeout in seconds and returns
# non-zero if the condition never became true.
# ---------------------------------------------------------------------------

# tcp_port_open HOST PORT — true if something accepts a TCP connection.
# Uses bash's built-in /dev/tcp (no `nc` dependency required).
tcp_port_open() {
  local host="$1" port="$2"
  (exec 3<>"/dev/tcp/${host}/${port}") 2>/dev/null
  local result=$?
  exec 3>&- 2>/dev/null || true
  exec 3<&- 2>/dev/null || true
  return "${result}"
}

# wait_for_tcp HOST PORT TIMEOUT_SECONDS
wait_for_tcp() {
  local host="$1" port="$2" timeout="${3:-30}"
  local waited=0
  while (( waited < timeout )); do
    tcp_port_open "${host}" "${port}" && return 0
    sleep 1
    waited=$((waited + 1))
  done
  return 1
}

# wait_for_http URL TIMEOUT_SECONDS — polls until curl gets any HTTP
# response (2xx/3xx/4xx all count as "the server answered"; a connection
# failure does not).
wait_for_http() {
  local url="$1" timeout="${2:-30}"
  local waited=0
  while (( waited < timeout )); do
    if curl --silent --fail --max-time 2 --output /dev/null "${url}"; then
      return 0
    fi
    sleep 1
    waited=$((waited + 1))
  done
  return 1
}

# ---------------------------------------------------------------------------
# Infrastructure (PostgreSQL / Redis, via docker compose) checks
# ---------------------------------------------------------------------------

postgres_ready() {
  local host="${POSTGRES_HOST:-localhost}" port="${POSTGRES_PORT:-5432}"
  if command -v pg_isready >/dev/null 2>&1; then
    pg_isready -h "${host}" -p "${port}" -q
  else
    tcp_port_open "${host}" "${port}"
  fi
}

redis_ready() {
  local host="${REDIS_HOST:-localhost}" port="${REDIS_PORT:-6379}"
  if command -v redis-cli >/dev/null 2>&1; then
    [[ "$(redis-cli -h "${host}" -p "${port}" ping 2>/dev/null)" == "PONG" ]]
  else
    tcp_port_open "${host}" "${port}"
  fi
}

# ---------------------------------------------------------------------------
# .env loading — mirrors Settings' own pydantic-settings behaviour (reads
# .env from the repo root) so this shell script's own checks (e.g. which
# port to poll) agree with what the Python processes will actually use,
# without duplicating Settings' defaults logic.
# ---------------------------------------------------------------------------

load_dotenv() {
  local env_file="${MIL_REPO_ROOT}/.env"
  [[ -f "${env_file}" ]] || return 1
  set -o allexport
  # shellcheck disable=SC1090
  source "${env_file}"
  set +o allexport
  return 0
}
