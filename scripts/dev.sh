#!/usr/bin/env bash
# Manage the local stack via docker compose, or run services directly.
#   dev.sh up | down | restart | logs | ps | local
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

cmd="${1:-up}"; shift || true

case "${cmd}" in
  up)
    log "Building and starting the full stack"
    compose up -d --build "$@"
    ok "Up. UI: http://localhost:8080  API: http://localhost:8000/docs"
    warn "If this is a fresh database, run 'just migrate'."
    ;;
  down)
    log "Stopping the stack"
    compose down "$@"
    ;;
  restart)
    compose down
    compose up -d --build
    ;;
  logs)
    compose logs -f "$@"
    ;;
  ps)
    compose ps "$@"
    ;;
  local)
    # Fast iteration without docker: requires `just setup` and running
    # Postgres/Redis (e.g. `docker compose up -d db redis`).
    log "Starting API (uvicorn) + frontend (vite) locally"
    ( cd "${BACKEND_DIR}" && "$(py_bin)" -m uvicorn app.main:app --reload --port 8000 ) &
    api_pid=$!
    ( cd "${FRONTEND_DIR}" && npm run dev ) &
    fe_pid=$!
    trap 'kill ${api_pid} ${fe_pid} 2>/dev/null || true' INT TERM
    wait
    ;;
  *)
    die "Unknown command '${cmd}'. Use: up|down|restart|logs|ps|local"
    ;;
esac
