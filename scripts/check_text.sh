#!/usr/bin/env bash
# Fail when tracked text carries an em/en dash or a dead tracker id.
#
# Dashes are a house-style rule: restructure the sentence instead. The
# exceptions below are not style, they are data. Job boards put " — " in their
# page titles and postings put "–" between salary bounds, so the matchers and
# the captured fixtures they read must keep the character verbatim. Deleting a
# dash there does not tidy prose, it breaks scraping.
#
# A tracker id (FRO-07, WS26) names a row in a backlog that no longer exists.
# 985 of them outlived docs/audit-backlog.md; the grep is cheap, the archaeology
# was not.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

# Paths whose dashes are third-party data, not our prose. Keep this list short
# and justify every entry: an over-broad exemption silently reopens the rule.
ALLOW_DASH=(
  # Careers page titles we match against: "Software Engineer — Google Careers".
  'backend/app/scrapers/url_detect'
  # Salary ranges arrive as "$120K – $180K"; the regex alternates -, –, — and "to".
  'backend/app/services/compensation_amounts.py'
  # Captured third-party HTML/JSON. It is evidence of what a site emits; editing
  # it makes the fixture lie and stops it catching a matcher regression.
  'backend/tests/fixtures/'
  # Feeds those real page titles in as input.
  'backend/tests/scrapers/test_url_detect.py'
  # This gate, and the rules it enforces, must name the characters they ban.
  'scripts/check_text.sh'
  'scripts/check_commit_msg.sh'
  'docs/conventions.md'
  # The gates' own tests carry a sample of every banned token on purpose: they
  # assert the gate rejects each one. Without them a gate could quietly stop
  # detecting anything and still look green.
  'backend/tests/devops/test_text_gate.py'
  'backend/tests/devops/test_commit_msg_gate.py'
)

allowed() {
  local file="$1" pat
  for pat in "${ALLOW_DASH[@]}"; do
    [[ "${file}" == *"${pat}"* ]] && return 0
  done
  return 1
}

cd "${REPO_ROOT}" || die "cannot enter ${REPO_ROOT}"

log "Text check (dashes, tracker ids)"
failed=0

# -I skips binary files; fixtures like .png would false-positive on byte runs.
while IFS=: read -r file _; do
  [[ -n "${file}" ]] || continue
  allowed "${file}" && continue
  printf '  %s: em/en dash. Restructure the sentence; do not swap in a comma.\n' \
    "${file}" >&2
  failed=1
done < <(git grep --untracked -In -e '—' -e '–' -- . 2>/dev/null | sort -u -t: -k1,1)

# — spelled as an escape keeps the dash in the output while hiding it from
# the grep above. That is not compliance, so ban the escape in source too.
while IFS=: read -r file _; do
  [[ -n "${file}" ]] || continue
  allowed "${file}" && continue
  case "${file}" in
    backend/tests/fixtures/*) continue ;;
  esac
  printf '  %s: unicode-escaped dash (\\u2013/\\u2014) still renders a dash.\n' \
    "${file}" >&2
  failed=1
done < <(git grep --untracked -In -e '\\u2013' -e '\\u2014' -- . 2>/dev/null | sort -u -t: -k1,1)

while IFS=: read -r file _; do
  [[ -n "${file}" ]] || continue
  # Same allowlist: the gates and their tests must name the ids they reject.
  allowed "${file}" && continue
  printf '  %s: tracker id (FRO-07 / WS26 style) resolves to nothing.\n' "${file}" >&2
  failed=1
done < <(
  git grep --untracked -InE '\b(AIA|API|APL|AUT|BIL|DAT|DOC|FRO|INB|NTF|OPS|POR|SCR|SVC|TST|XCT)-[0-9]+\b|\bWS[0-9]+\b' \
    -- . 2>/dev/null | sort -u -t: -k1,1
)

(( failed == 0 )) || die "Text check failed. See docs/conventions.md."
ok "Text check complete."
