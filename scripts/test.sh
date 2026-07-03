#!/usr/bin/env bash
# Run all tests (backend + frontend). Pass --backend or --frontend to scope.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

scope="${1:-all}"

run_backend() {
  log "Backend tests (pytest)"
  venv_tool pytest -q
}

run_frontend() {
  if [[ -d "${FRONTEND_DIR}/node_modules" ]]; then
    log "Frontend tests (vitest)"
    ( cd "${FRONTEND_DIR}" && npm run test --silent )
  else
    warn "frontend/node_modules missing; skipping. Run 'make setup'."
  fi
}

run_scripts() {
  log "Shell script validation"
  "${REPO_ROOT}/scripts/validate-shell-scripts.sh"
}

case "${scope}" in
  --backend)   run_backend ;;
  --frontend)  run_frontend ;;
  --scripts)   run_scripts ;;
  all)         run_backend; run_frontend; run_scripts ;;
  *)           die "Unknown scope '${scope}'. Use --backend|--frontend|--scripts|all" ;;
esac

ok "Tests complete."
