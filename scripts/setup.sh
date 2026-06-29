#!/usr/bin/env bash
# Install local toolchains: backend virtualenv + deps, frontend deps, git hooks.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

log "Setting up JobNotifier development environment"

# ---- preflight: check host toolchain ----
# These are NOT installed by this script (they are system/host tools). We only
# check and warn so missing tools are discoverable. On Ubuntu/WSL, see
# docs/runbook.md "Prerequisites & toolchain" for exact install commands.
log "Checking host tools (run inside WSL on Windows)"
have make    || warn "'make' not found — install it: sudo apt install -y make"
have docker  || warn "'docker' not found — needed for 'make up' (Docker Desktop WSL integration or native engine)."
docker compose version >/dev/null 2>&1 \
             || warn "'docker compose' plugin not found — needed for 'make up'."
have python3 || warn "'python3' not found — install it: sudo apt install -y python3 python3-venv"
have npm     || warn "'npm' not found — install Node.js 20+ (nodesource or nvm)."
# Deploy-only tools (safe to skip for local development):
have terraform || warn "'terraform' not found — only required for 'make deploy' (AWS)."
have aws       || warn "'aws' (AWS CLI v2) not found — only required for 'make deploy' (AWS)."

# ---- .env ----
if [[ ! -f "${REPO_ROOT}/.env" ]]; then
  cp "${REPO_ROOT}/.env.example" "${REPO_ROOT}/.env"
  ok "Created .env from .env.example (edit NTFY_DEFAULT_TOPIC)."
fi

# ---- backend ----
if have python3; then
  log "Creating backend virtualenv"
  python3 -m venv "${VENV_DIR}"
  "${VENV_DIR}/bin/python" -m pip install --upgrade pip >/dev/null
  log "Installing backend dependencies (editable, with dev extras)"
  "${VENV_DIR}/bin/pip" install -e "${BACKEND_DIR}[dev]"
  ok "Backend ready."
else
  warn "python3 not found; skipping backend setup."
fi

# ---- frontend ----
if have npm; then
  log "Installing frontend dependencies"
  ( cd "${FRONTEND_DIR}" && npm install )
  ok "Frontend ready."
  log "Installing browser extension dependencies"
  ( cd "${REPO_ROOT}/browser-extension" && npm install )
  ok "Browser extension ready."
else
  warn "npm not found; skipping frontend setup."
fi

# ---- pre-commit ----
if [[ -x "${VENV_DIR}/bin/pre-commit" ]]; then
  log "Installing git pre-commit hooks"
  ( cd "${REPO_ROOT}" && "${VENV_DIR}/bin/pre-commit" install )
  ok "Hooks installed."
fi

ok "Setup complete. Next: 'make up' then 'make migrate'."
