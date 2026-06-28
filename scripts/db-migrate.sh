#!/usr/bin/env bash
# Database migrations via Alembic.
#   db-migrate.sh upgrade            -> upgrade to head
#   db-migrate.sh downgrade [-1]     -> downgrade one step (or a target)
#   db-migrate.sh revision "message" -> autogenerate a new migration
#   db-migrate.sh current|history    -> inspect state
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

action="${1:-upgrade}"; shift || true

case "${action}" in
  upgrade)
    venv_tool alembic upgrade "${1:-head}"
    ok "Database upgraded."
    ;;
  downgrade)
    venv_tool alembic downgrade "${1:--1}"
    ;;
  revision)
    msg="${1:-}"
    [[ -n "${msg}" ]] || die 'Provide a message: make makemigration m="add x"'
    venv_tool alembic revision --autogenerate -m "${msg}"
    ok "Migration generated under backend/alembic/versions/ (review it!)."
    ;;
  current) venv_tool alembic current ;;
  history) venv_tool alembic history ;;
  *) die "Unknown action '${action}'. Use upgrade|downgrade|revision|current|history" ;;
esac
