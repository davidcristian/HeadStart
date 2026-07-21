#!/usr/bin/env bash
# Gate commit messages: Conventional Commits, no volatile references, no dashes.
#
# Rules exist because each drifted once the docs were the only thing enforcing
# them. Conventional Commits was written down in two places and 14 commits still
# broke it; tracker ids outlived the tracker by weeks. A message is cheap to fix
# at commit time and expensive to fix afterwards, because fixing it rewrites
# history and forces everyone to re-clone.
#
# Usage:
#   check_commit_msg.sh <file>          # a commit-msg hook passes the message file
#   check_commit_msg.sh --range A..B    # every commit in a range (CI)
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

# Bots write their own subjects and we do not rewrite them; see conventions.md.
BOT_AUTHORS_RE='dependabot|renovate|github-actions'

TYPES='feat|fix|docs|refactor|test|chore|ci|build'

fail() { printf '  %s\n' "$*" >&2; failed=1; }

check_text() {
  # $1 = full message, $2 = label for errors
  local msg="$1" label="$2" subject
  subject="$(printf '%s' "${msg}" | head -n1)"
  failed=0

  if ! printf '%s' "${subject}" | grep -qE "^(${TYPES})(\([a-z0-9_-]+\))?!?: .+"; then
    fail "subject is not a Conventional Commit: ${subject}"
    fail "  expected <type>(<scope>): <description>, type one of: ${TYPES//|/, }"
  fi

  # A PR number is only resolvable while the PR exists and the host keeps it.
  # GitHub's squash merge appends "(#123)" on its own, so strip it at merge time.
  if printf '%s' "${msg}" | grep -qE '\(#[0-9]+\)'; then
    fail "remove the PR reference '(#N)' from the message"
  fi
  if printf '%s' "${msg}" | grep -qiE '\b(PR|pull request) #[0-9]+'; then
    fail "remove the 'PR #N' reference from the message"
  fi

  # Dead-tracker ids: these outlived docs/audit-backlog.md by weeks.
  if printf '%s' "${msg}" | grep -qE '\b(AIA|API|APL|AUT|BIL|DAT|DOC|FRO|INB|NTF|OPS|POR|SCR|SVC|TST|XCT)-[0-9]+\b'; then
    fail "remove the tracker id; say what changed instead"
  fi
  if printf '%s' "${msg}" | grep -qE '\bWS[0-9]+\b'; then
    fail "remove the workstream id; say what changed instead"
  fi

  # Planning artefacts get renumbered or deleted; the commit outlives them.
  if printf '%s' "${msg}" | grep -qiE '\bphase [0-9]+|\b(catalog )?batch[- ]?[0-9]+\b'; then
    fail "remove the phase/batch number; describe the change itself"
  fi
  if printf '%s' "${msg}" | grep -qiE '\b(roadmap|backlog)\b'; then
    fail "do not reference the roadmap/backlog; describe the change itself"
  fi

  if printf '%s' "${msg}" | grep -q '—'; then
    fail "remove the em dash; restructure the sentence"
  fi
  if printf '%s' "${msg}" | grep -q '–'; then
    fail "remove the en dash; restructure the sentence"
  fi

  if (( failed )); then
    printf 'ERROR %s rejected:\n' "${label}" >&2
    return 1
  fi
  return 0
}

main() {
  local rc=0 checked=0
  if [[ "${1:-}" == "--range" ]]; then
    [[ -n "${2:-}" ]] || die "--range needs a revision range"
    log "Commit message check (${2})"
    # rev-list inside a process substitution hides its exit status, so an
    # unresolvable range would read as zero commits and the gate would pass
    # having checked nothing. Resolve it up front and fail loudly instead.
    local shas
    shas="$(git -C "${REPO_ROOT}" rev-list "${2}" 2>&1)" \
      || die "cannot resolve range '${2}': ${shas}"
    local sha
    while read -r sha; do
      [[ -n "${sha}" ]] || continue
      # Bot commits and host-generated merges are not ours to reword.
      if git -C "${REPO_ROOT}" log -1 --pretty=format:'%an %ae' "${sha}" \
          | grep -qiE "${BOT_AUTHORS_RE}"; then
        continue
      fi
      if [[ "$(git -C "${REPO_ROOT}" rev-list --no-walk --count --merges "${sha}")" == "1" ]]; then
        continue
      fi
      local msg
      msg="$(git -C "${REPO_ROOT}" log -1 --pretty=format:'%B' "${sha}")"
      check_text "${msg}" "commit $(git -C "${REPO_ROOT}" rev-parse --short "${sha}")" || rc=1
      checked=$((checked + 1))
    done <<< "${shas}"
    # Say how many were inspected. A silently-empty range reads identically to
    # a clean one otherwise.
    log "Inspected ${checked} commit(s)"
  else
    [[ -n "${1:-}" ]] || die "usage: check_commit_msg.sh <file> | --range A..B"
    [[ -f "${1}" ]] || die "no such message file: ${1}"
    # Strip comment lines git adds to the editor template.
    local msg
    msg="$(grep -v '^#' "${1}" || true)"
    # An empty message aborts the commit anyway; nothing to police.
    [[ -n "$(printf '%s' "${msg}" | tr -d '[:space:]')" ]] || exit 0
    check_text "${msg}" "commit message" || rc=1
  fi

  (( rc == 0 )) || die "Fix the message above. See docs/conventions.md."
  ok "Commit message check complete."
}

main "$@"
