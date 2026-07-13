#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# scripts/status.sh — current status of every platform component.
#
# Read-only: never starts, stops, or otherwise mutates anything. PID files
# are read, never written. Reports not just "running/stopped" but *why*
# something isn't healthy where that's knowable (stale PID file vs. never
# started vs. process alive but not answering its health check yet).
#
# Usage: scripts/status.sh
# ---------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/dev-common.sh
source "${SCRIPT_DIR}/lib/dev-common.sh"

cd "${MIL_REPO_ROOT}"
load_dotenv || true

API_PORT="${MIL_PORT:-8000}"
API_BASE="http://localhost:${API_PORT}"
FRONTEND_BASE="http://localhost:5173"

print_row() {
  local label="$1" status="$2" colour="$3" detail="${4:-}"
  printf '%-22s %s%s%s' "${label}" "${colour}" "${status}" "${C_RESET}"
  [[ -n "${detail}" ]] && printf '  %s(%s)%s' "${C_DIM}" "${detail}" "${C_RESET}"
  printf '\n'
}

# process_status KEY LABEL HEALTH_URL — HEALTH_URL is optional; when given,
# a live process that doesn't answer it is reported as degraded rather than
# a flat "Running", since that's a real, distinguishable state (still
# starting up, or crashed after fork without the OS having noticed yet).
process_status() {
  local key="$1" label="$2" health_url="${3:-}"
  local pid
  pid="$(running_pid "${key}")"

  if [[ -z "${pid}" ]]; then
    if is_stale_pid_file "${key}"; then
      print_row "${label}" "Stopped" "${C_RED}" "stale PID file — process exited, see logs/dev/${key}.log"
    else
      print_row "${label}" "Stopped" "${C_RED}" "not started — run scripts/dev-up.sh"
    fi
    return
  fi

  if [[ -n "${health_url}" ]]; then
    if curl --silent --fail --max-time 2 --output /dev/null "${health_url}"; then
      print_row "${label}" "Running" "${C_GREEN}" "pid ${pid}"
    else
      print_row "${label}" "Degraded" "${C_YELLOW}" "pid ${pid} alive, not answering ${health_url}"
    fi
  else
    print_row "${label}" "Running" "${C_GREEN}" "pid ${pid}"
  fi
}

infra_status() {
  local label="$1" check_fn="$2" host="$3" port="$4"
  if "${check_fn}"; then
    print_row "${label}" "Running" "${C_GREEN}" "${host}:${port}"
  elif tcp_port_open "${host}" "${port}"; then
    print_row "${label}" "Degraded" "${C_YELLOW}" "port ${port} open but not answering a ping — still starting?"
  else
    print_row "${label}" "Stopped" "${C_RED}" "not reachable at ${host}:${port} — run: docker compose up -d"
  fi
}

log_step "MIL Enterprise Platform — status"
echo ""

process_status api "API" "${API_BASE}/v1/ready"
process_status frontend "Frontend" "${FRONTEND_BASE}"
infra_status "Redis" redis_ready "${REDIS_HOST:-localhost}" "${REDIS_PORT:-6379}"
infra_status "PostgreSQL" postgres_ready "${POSTGRES_HOST:-localhost}" "${POSTGRES_PORT:-5432}"
process_status worker-ocr "OCR Worker"
process_status worker-extraction "Extraction Worker"
process_status worker-finding "Finding Worker"
process_status worker-policy "Policy Worker"
process_status worker-review "Review Worker"

echo ""
echo "Logs:      logs/dev/<component>.log"
echo "Start:     scripts/dev-up.sh"
echo "Stop:      scripts/dev-down.sh"
