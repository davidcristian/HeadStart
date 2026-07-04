#!/usr/bin/env bash
# Syntax-check shell scripts and smoke-test --help on orchestration entrypoints.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

log "Shell script syntax check"
for script in "${REPO_ROOT}"/scripts/*.sh; do
  bash -n "${script}" || die "Syntax error in ${script}"
done

log "Backend lockfiles present with hashes"
for lock in requirements.txt requirements-dev.txt requirements-playwright.txt; do
  path="${BACKEND_DIR}/${lock}"
  [[ -f "${path}" ]] || die "Missing ${path} — run 'just lock-backend'"
  grep -q -- '--hash=' "${path}" || die "${path} has no package hashes"
done

log "aws-first-deploy.sh --help"
"${REPO_ROOT}/scripts/aws-first-deploy.sh" --help >/dev/null

ok "Shell script validation complete."
