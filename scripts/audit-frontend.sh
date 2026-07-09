#!/usr/bin/env bash
# Fail CI/local gates when frontend deps have high/critical advisories (FRO-12).
# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

log "Frontend dependency audit (npm audit --audit-level=high)"
( cd "${FRONTEND_DIR}" && npm audit --audit-level=high )
ok "Frontend npm audit clean at high+."
