#!/usr/bin/env bash
# Type-check backend (mypy) and frontend (tsc --noEmit).
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

log "Backend types (mypy)"
venv_tool mypy app

if [[ -d "${FRONTEND_DIR}/node_modules" ]]; then
  log "Frontend types (tsc)"
  ( cd "${FRONTEND_DIR}" && npm run typecheck --silent )
else
  warn "frontend/node_modules missing; skipping tsc."
fi

ok "Type-check complete."
