#!/usr/bin/env bash
# Load example data (sources + a sample search + ntfy target) for local dev.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

log "Seeding example data"
py -m app.cli.seed "$@"
ok "Seed complete."
