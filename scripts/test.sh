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

run_extension() {
  if [[ -d "${REPO_ROOT}/browser-extension/node_modules" ]]; then
    log "Browser extension tests (vitest)"
    ( cd "${REPO_ROOT}/browser-extension" && npm run test --silent )
  else
    warn "browser-extension/node_modules missing; skipping. Run 'npm install' in browser-extension/."
  fi
}

run_scripts() {
  log "Shell script validation"
  "${REPO_ROOT}/scripts/validate-shell-scripts.sh"
}

case "${scope}" in
  --backend)   run_backend ;;
  --frontend)  run_frontend ;;
  --extension) run_extension ;;
  --scripts)   run_scripts ;;
  all)         run_backend; run_frontend; run_extension; run_scripts ;;
  *)           die "Unknown scope '${scope}'. Use --backend|--frontend|--extension|--scripts|all" ;;
esac

ok "Tests complete."
