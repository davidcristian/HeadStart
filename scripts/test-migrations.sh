#!/usr/bin/env bash
# Apply every alembic migration from scratch against a real Postgres.
#
# Backend unit tests build schema via SQLite ``create_all``, so dialect-specific
# migration SQL (raw UPDATE/DELETE, partial indexes, boolean literals, ...) is
# never exercised against the production dialect by `just test`. This gate
# boots a disposable Postgres in docker, runs `alembic upgrade head` on an
# empty database, then `alembic check` so ORM metadata cannot drift from the
# applied migrations. CI runs it on every push/PR; run locally via
# `just test-migrations`.
#
# Full downgrade-to-base is intentionally not gated: irreversible data
# migrations (e.g. plan slug rewrite, GDPR redaction) no-op their downgrade().
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

export DATABASE_URL="postgresql+psycopg://${PG_USER}:${PG_PASSWORD}@127.0.0.1:${port}/${PG_DB}"

log "alembic upgrade head (empty database)"
venv_tool alembic upgrade head

# Fail if the live schema diverges from Base.metadata (model/migration drift).
log "alembic check (metadata vs applied migrations)"
venv_tool alembic check

ok "All migrations apply cleanly on Postgres and match ORM metadata."
