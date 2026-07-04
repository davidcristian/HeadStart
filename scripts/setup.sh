#!/usr/bin/env bash
# Install local toolchains: backend virtualenv + deps, frontend deps, git hooks.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

log "Setting up HeadStart development environment"

# ---- preflight: check host toolchain ----
# These are NOT installed by this script (they are system/host tools). We only
# check and warn so missing tools are discoverable. On Ubuntu/WSL, see
# docs/runbook.md "Prerequisites & toolchain" for exact install commands.
log "Checking host tools (run inside WSL on Windows)"
have just    || warn "'just' not found — install it: sudo apt install -y just (or see https://just.systems)"
have docker  || warn "'docker' not found — needed for 'just up' (Docker Desktop WSL integration or native engine)."
docker compose version >/dev/null 2>&1 \
             || warn "'docker compose' plugin not found — needed for 'just up'."
have python3 || warn "'python3' not found — install it: sudo apt install -y python3 python3-venv"
have npm     || warn "'npm' not found — install Node.js 20+ (nodesource or nvm)."
# Deploy-only tools (safe to skip for local development):
have terraform || warn "'terraform' not found — only required for 'just deploy' (AWS)."
have aws       || warn "'aws' (AWS CLI v2) not found — only required for 'just deploy' (AWS)."

# ---- .env ----
if [[ ! -f "${REPO_ROOT}/.env" ]]; then
  cp "${REPO_ROOT}/.env.example" "${REPO_ROOT}/.env"
  ok "Created .env from .env.example (edit NTFY_DEFAULT_TOPIC)."
fi

# ---- backend ----
if have python3; then
  log "Creating backend virtualenv"
  python3 -m venv "${VENV_DIR}"
  log "Installing backend dependencies from hashed lockfile (dev)"
  "${REPO_ROOT}/scripts/install-backend.sh" --dev
  ok "Backend ready."
else
  warn "python3 not found; skipping backend setup."
fi

# ---- frontend ----
if have npm; then
  log "Installing frontend dependencies"
  ( cd "${FRONTEND_DIR}" && npm install )
  ok "Frontend ready."
else
  warn "npm not found; skipping frontend setup."
fi

# ---- pre-commit ----
if [[ -x "${VENV_DIR}/bin/pre-commit" ]]; then
  log "Installing git pre-commit hooks"
  ( cd "${REPO_ROOT}" && "${VENV_DIR}/bin/pre-commit" install )
  ok "Hooks installed."
fi

ok "Setup complete. Next: 'just up' then 'just migrate'."
