#!/usr/bin/env bash
# Fail CI/local gates when hashed backend lockfiles have known advisories (OPS-19).
# Uses --disable-pip so hashed pins are audited without a throwaway venv.
# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

log "Backend dependency audit (pip-audit on hashed lockfiles)"

if ! py -c "import pip_audit" >/dev/null 2>&1; then
  die "pip-audit not installed. Run './scripts/install-backend.sh --dev' first."
fi

for lock in requirements.txt requirements-dev.txt requirements-playwright.txt; do
  path="${BACKEND_DIR}/${lock}"
  [[ -f "${path}" ]] || die "Missing lockfile ${path}. Run 'just lock-backend'."
  grep -q -- '--hash=' "${path}" || die "Lockfile ${path} is missing package hashes"
done

py -m pip_audit \
  --disable-pip \
  --progress-spinner off \
  -r "${BACKEND_DIR}/requirements.txt" \
  -r "${BACKEND_DIR}/requirements-dev.txt" \
  -r "${BACKEND_DIR}/requirements-playwright.txt"

ok "Backend pip-audit clean on hashed lockfiles."
