#!/usr/bin/env bash
# Full quality gate: lint + typecheck + tests (same entrypoint local and CI).
# Pass --backend | --frontend | --scripts to scope; default is all.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

scope="${1:-all}"

case "${scope}" in
  --backend)
    "${REPO_ROOT}/scripts/lint.sh" --backend
    "${REPO_ROOT}/scripts/typecheck.sh" --backend
    "${REPO_ROOT}/scripts/test.sh" --backend
    ;;
  --frontend)
    "${REPO_ROOT}/scripts/lint.sh" --frontend
    "${REPO_ROOT}/scripts/typecheck.sh" --frontend
    "${REPO_ROOT}/scripts/test.sh" --frontend
    ;;
  --scripts)
    "${REPO_ROOT}/scripts/test.sh" --scripts
    ;;
  all)
    "${REPO_ROOT}/scripts/lint.sh"
    "${REPO_ROOT}/scripts/typecheck.sh"
    "${REPO_ROOT}/scripts/test.sh"
    ;;
  *)
    die "Unknown scope '${scope}'. Use --backend|--frontend|--scripts|all"
    ;;
esac

ok "Check complete."
