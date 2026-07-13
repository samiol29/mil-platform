#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# scripts/dev-down.sh — cleanly stop everything scripts/dev-up.sh started.
#
# Stops the frontend, backend API, and all five workers (SIGTERM, then
# SIGKILL after a grace period if a process doesn't exit), removes their PID
# files, and prints a shutdown summary. Deliberately leaves PostgreSQL,
# Redis, and MinIO running — they're shared, stateful infrastructure managed
# by docker compose, not per-dev-session processes; stop them explicitly
# with `docker compose down` if you actually want them down too.
#
# Safe to run repeatedly, and safe to run when nothing is up.
#
# Usage: scripts/dev-down.sh
# ---------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/dev-common.sh
source "${SCRIPT_DIR}/lib/dev-common.sh"

cd "${MIL_REPO_ROOT}"

log_step "Stopping MIL Enterprise Platform"

# Stop in the reverse order dev-up.sh starts things: frontend first (the
# outermost layer), then the API, then the workers underneath it — no
# process here depends on another staying up during shutdown, but this
# order matches how a human would expect the stack to unwind.
stop_managed frontend "Frontend"
stop_managed api "Backend API"
stop_managed worker-ocr "OCR Worker"
stop_managed worker-extraction "Extraction Worker"
stop_managed worker-finding "Finding Worker"
stop_managed worker-policy "Policy Worker"
stop_managed worker-review "Review Worker"

echo ""
echo "${C_BOLD}${C_GREEN}MIL Enterprise Platform stopped.${C_RESET}"
echo ""
echo "PostgreSQL and Redis (and MinIO) were left running — they're shared"
echo "infrastructure, not part of this dev session. To stop them too:"
echo "  docker compose down"
echo ""
echo "To bring everything back up:  scripts/dev-up.sh"
