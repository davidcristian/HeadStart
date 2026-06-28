#!/usr/bin/env bash
# Lint backend (ruff) and frontend (eslint).
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

log "Backend lint (ruff)"
venv_tool ruff check app tests

log "Backend format check (black)"
venv_tool black --check app tests

if [[ -d "${FRONTEND_DIR}/node_modules" ]]; then
  log "Frontend lint (eslint)"
  ( cd "${FRONTEND_DIR}" && npm run lint --silent )
else
  warn "frontend/node_modules missing; skipping eslint."
fi

ok "Lint complete."
