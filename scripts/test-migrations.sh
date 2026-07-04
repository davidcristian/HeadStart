#!/usr/bin/env bash
# Apply every alembic migration from scratch against a real Postgres.
#
# Backend tests run on in-memory SQLite, so dialect-specific migration SQL
# (raw UPDATE/DELETE statements, partial indexes, boolean literals, ...) is
# never exercised against the production dialect by `just test`. This gate
# boots a disposable Postgres in docker, runs `alembic upgrade head` on an
# empty database, and tears everything down. CI runs it on every push/PR;
# run it locally via `just test-migrations`.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

have docker || die "docker is required: this gate boots a disposable Postgres container."

# Same major version as docker-compose.yml and the AWS database.
PG_IMAGE="postgres:16-alpine"
PG_USER="headstart"
PG_PASSWORD="headstart"
PG_DB="headstart_migration_test"
CONTAINER="headstart-migration-test-$$"

cleanup() { docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true; }
trap cleanup EXIT

log "Starting disposable Postgres (${PG_IMAGE})"
docker run -d --rm \
  --name "${CONTAINER}" \
  -e POSTGRES_USER="${PG_USER}" \
  -e POSTGRES_PASSWORD="${PG_PASSWORD}" \
  -e POSTGRES_DB="${PG_DB}" \
  --tmpfs /var/lib/postgresql/data \
  -p 127.0.0.1::5432 \
  "${PG_IMAGE}" >/dev/null

port="$(docker port "${CONTAINER}" 5432/tcp | head -n1 | awk -F: '{print $NF}')"
[[ -n "${port}" ]] || die "Could not determine the mapped Postgres port."

# -h 127.0.0.1 forces TCP so the short-lived unix-socket-only server that
# initdb starts during first boot cannot be mistaken for the real one.
log "Waiting for Postgres on 127.0.0.1:${port}"
ready=""
for _ in $(seq 1 60); do
  if docker exec "${CONTAINER}" pg_isready -q -h 127.0.0.1 -U "${PG_USER}" -d "${PG_DB}" 2>/dev/null; then
    ready=1
    break
  fi
  sleep 1
done
[[ "${ready}" == 1 ]] || die "Postgres did not become ready within 60s."

log "alembic upgrade head (empty database)"
DATABASE_URL="postgresql+psycopg://${PG_USER}:${PG_PASSWORD}@127.0.0.1:${port}/${PG_DB}" \
  venv_tool alembic upgrade head

ok "All migrations apply cleanly on Postgres."
