#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# scripts/dev-up.sh — bring the entire MIL platform online with one command.
#
# Starts, in order: infrastructure (PostgreSQL, Redis, MinIO via docker
# compose) → migrations → API → the five real pipeline workers → frontend.
# Waits on a real readiness signal for each piece (an HTTP health check for
# the API/frontend, TCP/pg_isready/redis-cli for infrastructure, "did the
# process survive its startup window" for workers, which have no HTTP
# surface) rather than a fixed sleep. Safe to re-run: every already-running
# piece is detected and left alone, never duplicated.
#
# Usage: scripts/dev-up.sh
# ---------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/dev-common.sh
source "${SCRIPT_DIR}/lib/dev-common.sh"

cd "${MIL_REPO_ROOT}"

FAILURES=()

# Refuse to start on a nearly full disk — a dev session must never be the
# thing that pushes the machine over the edge.
FREE_MB="$(free_disk_mb "${MIL_REPO_ROOT}")"
if (( FREE_MB < MIL_DEV_MIN_FREE_MB )); then
  log_err "Only ${FREE_MB} MB free on the repo's disk (need ${MIL_DEV_MIN_FREE_MB} MB). Free up space first."
  exit 1
fi

# ---------------------------------------------------------------------------
# 1. Python virtual environment
# ---------------------------------------------------------------------------

log_step "1/8 — Python virtual environment"

if [[ ! -d "${MIL_VENV_DIR}" ]]; then
  log_err "No virtual environment found at ${MIL_VENV_DIR}."
  log_err "Create one first:  python3 -m venv .venv && source .venv/bin/activate && pip install -e \".[dev]\""
  exit 1
fi

# shellcheck source=/dev/null
source "${MIL_VENV_DIR}/bin/activate"
log_ok "Virtual environment activated ($(command -v python3))."

if ! python3 -c "import uvicorn, alembic, mil, workers, main" >/dev/null 2>&1; then
  log_err "The virtual environment exists but the platform isn't installed into it."
  log_err "Run:  source .venv/bin/activate && pip install -e \".[dev]\""
  exit 1
fi
log_ok "Platform package importable (editable install detected)."

# ---------------------------------------------------------------------------
# 2. Environment variables
# ---------------------------------------------------------------------------

log_step "2/8 — Environment variables"

if load_dotenv; then
  log_ok ".env loaded from repo root."
else
  log_warn "No .env file found at repo root — falling back to shell environment + application defaults."
  log_warn "Copy .env.example to .env and fill in secrets for a normal local setup."
fi

# GEMINI_API_KEY is a hard requirement: OCR/Extraction/Inference all default
# to the Gemini provider with no mock fallback in any environment (see
# docs/deployment/README.md §3) — the API and every worker that touches
# documents will fail at container-build time without it. Fail fast here
# with a clear message instead of watching five processes crash one by one.
if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  log_err "GEMINI_API_KEY is not set. OCR, Extraction, and Inference have no mock fallback and"
  log_err "will refuse to start without it. Set it in .env (see .env.example) and re-run."
  exit 1
fi
log_ok "GEMINI_API_KEY is set."

MIL_HOST_CHECK="${MIL_HOST:-0.0.0.0}"
API_PORT="${MIL_PORT:-8000}"
API_BASE="http://localhost:${API_PORT}"
FRONTEND_PORT=5173
FRONTEND_BASE="http://localhost:${FRONTEND_PORT}"

# ---------------------------------------------------------------------------
# 3. Infrastructure — PostgreSQL, Redis (and MinIO, the object store the
#    same docker-compose stack provisions alongside them)
# ---------------------------------------------------------------------------

log_step "3/8 — Infrastructure (PostgreSQL, Redis, MinIO)"

if postgres_ready && redis_ready; then
  log_ok "PostgreSQL and Redis already running — skipping docker compose."
else
  log_info "Starting infrastructure via docker compose..."
  (cd "${MIL_REPO_ROOT}" && docker compose up -d)
fi

if wait_for_tcp "${POSTGRES_HOST:-localhost}" "${POSTGRES_PORT:-5432}" 30 && postgres_ready; then
  log_ok "PostgreSQL is ready."
else
  log_err "PostgreSQL did not become ready within 30s. Check: docker compose logs postgres"
  exit 1
fi

if wait_for_tcp "${REDIS_HOST:-localhost}" "${REDIS_PORT:-6379}" 30 && redis_ready; then
  log_ok "Redis is ready."
else
  log_err "Redis did not become ready within 30s. Check: docker compose logs redis"
  exit 1
fi

# ---------------------------------------------------------------------------
# 4. Migrations
# ---------------------------------------------------------------------------

log_step "4/8 — Database migrations"

if alembic upgrade head; then
  log_ok "Migrations up to date."
else
  log_err "Migration failed — see output above."
  exit 1
fi

# ---------------------------------------------------------------------------
# 5. Backend API
# ---------------------------------------------------------------------------

log_step "5/8 — Backend API"

start_managed api "Backend API" "${MIL_REPO_ROOT}" \
  uvicorn main:app --host "${MIL_HOST_CHECK}" --port "${API_PORT}" --reload --reload-dir src

if wait_for_http "${API_BASE}/v1/ready" 45; then
  log_ok "API is ready (${API_BASE}/v1/ready)."
else
  log_err "API did not become ready within 45s. Last log lines:"
  tail -n 20 "$(log_file_for api)" >&2 || true
  FAILURES+=("Backend API")
fi

# ---------------------------------------------------------------------------
# 6. Workers
#
# Exactly the five real pipeline workers this platform has (audited from
# src/workers/ and the existing `make run-worker` target) — Document
# ingestion (OCR), Extraction, Finding generation, Policy evaluation, and
# Review handoff. There is no separate "notification worker": notifications
# are written synchronously by NotificationService within the same request/
# job transaction that triggers them (see mil.notification), not consumed
# from a queue by a standalone process — so none is started here.
# ---------------------------------------------------------------------------

log_step "6/8 — Workers (OCR, Extraction, Finding, Policy, Review)"

WORKER_KEYS=(worker-ocr worker-extraction worker-finding worker-policy worker-review)
WORKER_LABELS=("OCR Worker" "Extraction Worker" "Finding Worker" "Policy Worker" "Review Worker")
WORKER_SHORT_NAMES=(OCR Extraction Finding Policy Review)
WORKER_MODULES=(workers.document_pipeline workers.extraction_pipeline workers.finding_pipeline workers.policy_pipeline workers.review_pipeline)

for i in "${!WORKER_KEYS[@]}"; do
  start_managed "${WORKER_KEYS[$i]}" "${WORKER_LABELS[$i]}" "${MIL_REPO_ROOT}" \
    python3 -m "${WORKER_MODULES[$i]}"
done

# Workers expose no HTTP surface, so "healthy" means "still alive after the
# window in which a bad config (missing provider, bad DB creds) would have
# crashed it on the first job-queue connection attempt" — not a fabricated
# health check.
sleep 2
for i in "${!WORKER_KEYS[@]}"; do
  key="${WORKER_KEYS[$i]}"
  label="${WORKER_LABELS[$i]}"
  pid="$(running_pid "${key}")"
  if [[ -n "${pid}" ]]; then
    log_ok "${label} is running (pid ${pid})."
  else
    log_err "${label} exited immediately. Last log lines:"
    tail -n 20 "$(log_file_for "${key}")" >&2 || true
    FAILURES+=("${label}")
  fi
done

# ---------------------------------------------------------------------------
# 7. Frontend
# ---------------------------------------------------------------------------

log_step "7/8 — Frontend"

if [[ ! -d "${MIL_FRONTEND_DIR}/node_modules" ]]; then
  log_err "frontend/node_modules is missing. Run:  (cd frontend && npm install)"
  exit 1
fi

start_managed frontend "Frontend" "${MIL_FRONTEND_DIR}" npm run dev -- --port "${FRONTEND_PORT}"

if wait_for_http "${FRONTEND_BASE}" 45; then
  log_ok "Frontend is ready (${FRONTEND_BASE})."
else
  log_err "Frontend did not become ready within 45s. Last log lines:"
  tail -n 20 "$(log_file_for frontend)" >&2 || true
  FAILURES+=("Frontend")
fi

# ---------------------------------------------------------------------------
# 8. Summary
# ---------------------------------------------------------------------------

log_step "8/8 — Summary"

if (( ${#FAILURES[@]} > 0 )); then
  echo ""
  log_err "MIL Enterprise Platform started with problems:"
  for f in "${FAILURES[@]}"; do
    log_err "  - ${f}"
  done
  echo ""
  echo "Run scripts/status.sh for the current state, or check logs under logs/dev/."
  exit 1
fi

echo ""
echo "${C_BOLD}${C_GREEN}MIL Enterprise Platform started successfully${C_RESET}"
echo ""
echo "${C_BOLD}Frontend:${C_RESET}"
echo "  ${FRONTEND_BASE}"
echo ""
echo "${C_BOLD}Backend API:${C_RESET}"
echo "  ${API_BASE}"
echo ""
echo "${C_BOLD}Swagger:${C_RESET}"
echo "  ${API_BASE}/v1/docs"
echo ""
echo "${C_BOLD}Health:${C_RESET}"
echo "  ${API_BASE}/v1/health"
echo ""
echo "${C_BOLD}OpenAPI:${C_RESET}"
echo "  ${API_BASE}/v1/openapi.json"
echo ""
echo "${C_BOLD}Workers:${C_RESET}"
for name in "${WORKER_SHORT_NAMES[@]}"; do
  echo "  ${C_GREEN}✓${C_RESET} ${name}"
done
echo ""
echo "${C_BOLD}Database:${C_RESET}"
echo "  ${C_GREEN}✓${C_RESET} PostgreSQL"
echo ""
echo "${C_BOLD}Cache:${C_RESET}"
echo "  ${C_GREEN}✓${C_RESET} Redis"
echo ""
echo "────────────────────────"
echo "Stop everything:   scripts/dev-down.sh"
echo "Check status:      scripts/status.sh"
echo "Logs:               logs/dev/  (capped at ${MIL_DEV_LOG_MAX_MB} MB x $((MIL_DEV_LOG_BACKUPS + 1)) files per process)"
