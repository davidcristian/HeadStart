#!/usr/bin/env bash
# Container entrypoint: one image, multiple roles selected by the first argument.
set -euo pipefail

CELERY_APP="app.worker.celery_app:celery_app"

case "${1:-api}" in
  api)
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
    ;;
  worker)
    exec celery -A "${CELERY_APP}" worker --loglevel="${LOG_LEVEL:-INFO}"
    ;;
  beat)
    exec celery -A "${CELERY_APP}" beat --loglevel="${LOG_LEVEL:-INFO}"
    ;;
  migrate)
    exec alembic upgrade head
    ;;
  *)
    # Fall through to an arbitrary command (useful for debugging).
    exec "$@"
    ;;
esac
