#!/usr/bin/env bash
# Production SPA build (tsc + vite). CI uses this so the build step cannot
# drift from a documented just/scripts entrypoint.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_frontend_deps
log "Frontend build (tsc + vite)"
( cd "${FRONTEND_DIR}" && npm run build --silent )

ok "Frontend build complete."
