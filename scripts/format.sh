#!/usr/bin/env bash
# Auto-format backend (black + ruff --fix) and frontend (prettier).
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

log "Backend format (ruff --fix + black)"
venv_tool ruff check --fix app tests
venv_tool black app tests

if [[ -d "${FRONTEND_DIR}/node_modules" ]]; then
  log "Frontend format (prettier)"
  ( cd "${FRONTEND_DIR}" && npm run format --silent )
else
  warn "frontend/node_modules missing; skipping prettier."
fi

ok "Format complete."
