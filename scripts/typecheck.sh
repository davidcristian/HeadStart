#!/usr/bin/env bash
# Type-check backend (mypy) and frontend (tsc --noEmit).
# Pass --backend or --frontend to scope (CI uses this); default is all.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

scope="${1:-all}"

run_backend() {
  log "Backend types (mypy)"
  venv_tool mypy app
}

run_frontend() {
  require_frontend_deps
  log "Frontend types (tsc)"
  ( cd "${FRONTEND_DIR}" && npm run typecheck --silent )
}

case "${scope}" in
  --backend)  run_backend ;;
  --frontend) run_frontend ;;
  all)        run_backend; run_frontend ;;
  *)          die "Unknown scope '${scope}'. Use --backend|--frontend|all" ;;
esac

ok "Type-check complete."
