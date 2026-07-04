#!/usr/bin/env bash
# Lint backend (ruff + black + repo LOC gate) and frontend (eslint).
# Pass --backend or --frontend to scope (CI uses this); default is all.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

scope="${1:-all}"

run_backend() {
  log "Backend lint (ruff)"
  venv_tool ruff check app tests

  log "Backend format check (black)"
  venv_tool black --check app tests

  # The LOC gate is repo-wide; it rides with the backend scope so CI runs it
  # exactly once.
  "${REPO_ROOT}/scripts/check_loc.sh"
}

run_frontend() {
  require_frontend_deps
  log "Frontend lint (eslint)"
  ( cd "${FRONTEND_DIR}" && npm run lint --silent )
}

case "${scope}" in
  --backend)  run_backend ;;
  --frontend) run_frontend ;;
  all)        run_backend; run_frontend ;;
  *)          die "Unknown scope '${scope}'. Use --backend|--frontend|all" ;;
esac

ok "Lint complete."
