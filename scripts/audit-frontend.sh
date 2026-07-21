#!/usr/bin/env bash
# Fail CI/local gates when frontend deps have high/critical advisories.
#
# npm audit has no allowlist of its own, so the JSON report is filtered here.
# Only the advisories named in ALLOWED_ADVISORIES are skipped; every other high
# or critical finding still fails the gate, and an entry whose advisory id
# cannot be resolved fails too (an unreadable report must not read as clean).
# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

# GHSA-qwww-vcr4-c8h2: React Router RSC mode CSRF bypass, high, affecting
# 7.12.0 through 8.2.0. This app renders a plain SPA and never turns on RSC, so
# the affected request path does not exist in the bundle. Holding at 6.x to dodge
# it would reinstate three moderate advisories that DO apply here, two of them
# open redirects in <Link> and useNavigate. Remove this entry once a fixed 7.x
# is published.
ALLOWED_ADVISORIES="GHSA-qwww-vcr4-c8h2"

log "Frontend dependency audit (npm audit, high+, allowlist applied)"

require_frontend_deps

audit_json="$(mktemp)"
# shellcheck disable=SC2064  # expand the path now; the temp file is per run.
trap "rm -f '${audit_json}'" EXIT

# npm audit exits nonzero whenever it finds anything, including an allowlisted
# entry, so its status carries no signal. The filter below decides the outcome.
( cd "${FRONTEND_DIR}" && npm audit --json >"${audit_json}" 2>/dev/null ) || true
[[ -s "${audit_json}" ]] || die "npm audit produced no report"

"$(py_bin)" - "${audit_json}" "${ALLOWED_ADVISORIES}" <<'PY'
import json
import sys

report_path, allowed_csv = sys.argv[1], sys.argv[2]
allowed = {item for item in allowed_csv.split(",") if item}

with open(report_path, encoding="utf-8") as handle:
    try:
        report = json.load(handle)
    except json.JSONDecodeError as exc:
        sys.exit(f"ERROR could not parse the npm audit report: {exc}")

vulns = report.get("vulnerabilities") or {}


def advisory_ids(name, seen=None):
    """Collect GHSA ids for a package, following string `via` links upward.

    npm reports a transitively affected package as `via: ["<parent>"]` with no
    advisory of its own, so the id has to come from whichever ancestor owns it.
    """
    seen = seen if seen is not None else set()
    if name in seen:
        return set()
    seen.add(name)
    found = set()
    for via in vulns.get(name, {}).get("via") or []:
        if isinstance(via, dict):
            ghsa = (via.get("url") or "").rstrip("/").rsplit("/", 1)[-1]
            if ghsa.startswith("GHSA-"):
                found.add(ghsa)
        elif isinstance(via, str):
            found |= advisory_ids(via, seen)
    return found


blocking, skipped = [], []
for name, meta in sorted(vulns.items()):
    if meta.get("severity") not in ("high", "critical"):
        continue
    ids = advisory_ids(name)
    # Fail closed: an unresolvable id is treated as blocking, never as allowed.
    if ids and ids <= allowed:
        skipped.append((name, meta["severity"], sorted(ids)))
    else:
        blocking.append((name, meta["severity"], sorted(ids) or ["unidentified"]))

for name, severity, ids in skipped:
    print(f"  allowlisted: {name} ({severity}) {','.join(ids)}")

if blocking:
    print("Blocking advisories at high or critical:", file=sys.stderr)
    for name, severity, ids in blocking:
        print(f"  {name} ({severity}) {','.join(ids)}", file=sys.stderr)
    sys.exit(1)
PY

ok "Frontend npm audit clean at high+ (allowlisted advisories excepted)."
