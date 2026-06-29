#!/usr/bin/env bash
# Syntax-check shell scripts and smoke-test --help on orchestration entrypoints.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

log "Shell script syntax check"
for script in "${REPO_ROOT}"/scripts/*.sh; do
  bash -n "${script}" || die "Syntax error in ${script}"
done

log "aws-first-deploy.sh --help"
"${REPO_ROOT}/scripts/aws-first-deploy.sh" --help >/dev/null

ok "Shell script validation complete."
