#!/usr/bin/env bash
# Syntax-check shell scripts (bash -n + shellcheck) and smoke-test --help
# on orchestration entrypoints. OPS-65: shellcheck catches quoting /
# unbound-variable bugs that bash -n cannot see.
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

# Severity floor: error + warning fail the gate; style/info do not.
# -x follows `source lib.sh` so shared helpers are analyzed too.

log "Shell script syntax check"
for script in "${REPO_ROOT}"/scripts/*.sh; do
  bash -n "${script}" || die "Syntax error in ${script}"
done

log "ShellCheck static analysis (OPS-65)"
have shellcheck || die "shellcheck not found — install it: sudo apt install -y shellcheck (see docs/runbook.md)"
shellcheck -x -S warning "${REPO_ROOT}"/scripts/*.sh \
  || die "shellcheck reported warnings/errors in scripts/*.sh"

log "Backend lockfiles present with hashes"
for lock in requirements.txt requirements-dev.txt requirements-playwright.txt; do
  path="${BACKEND_DIR}/${lock}"
  [[ -f "${path}" ]] || die "Missing ${path} — run 'just lock-backend'"
  grep -q -- '--hash=' "${path}" || die "${path} has no package hashes"
done

log "aws-first-deploy.sh --help"
"${REPO_ROOT}/scripts/aws-first-deploy.sh" --help >/dev/null

ok "Shell script validation complete."
