# 0013. Named allowlist for frontend security advisories

- **Status:** Accepted
- **Date:** 2026-07-21

## Context

`just audit-frontend` ran `npm audit --audit-level=high` and failed CI on any
high or critical advisory. That worked until react-router forced a choice where
both options carry advisories.

`react-router-dom` 6.30.4 is subject to three **moderate** advisories, all fixed
in 7.18.0:

- open redirect via backslash in `<Link>` and `useNavigate`
- arbitrary constructor injection via `deserializeErrors()`
- open redirect leading to XSS

The first two are reachable from a plain single page app, so they describe real
exposure here. Upgrading to 7.18.1 clears all three but enters the range of
[GHSA-qwww-vcr4-c8h2](https://github.com/advisories/GHSA-qwww-vcr4-c8h2), a
**high** CSRF bypass in React Router's RSC mode. Its range has since been revised
upward to `>=7.12.0 <8.3.0`, first patched in 8.3.0. No fixed 7.x exists and no
8.x is published at all, so there is no version that avoids both, and each patch
release inside 7.x stays inside the advisory.

This app renders a plain SPA and never enables RSC, so the code path the high
advisory describes is not present in the bundle. Staying on 6.x to keep the
gate green would therefore trade two applicable moderate issues for one
inapplicable high one, which is the wrong direction.

## Decision

Upgrade to `react-router-dom` 7.18.1 and give `scripts/audit-frontend.sh` a
named allowlist. The script now reads the `npm audit --json` report and skips
only the advisory ids in `ALLOWED_ADVISORIES`, currently just
`GHSA-qwww-vcr4-c8h2`, with the reasoning recorded inline.

The filter **fails closed**:

- any other high or critical advisory still fails the gate
- an entry whose advisory id cannot be resolved is treated as blocking
- a report that cannot be parsed is an error, never a pass

Transitively affected packages are reported by npm as `via: ["<parent>"]` with
no advisory of their own, so the filter walks those links to the ancestor that
owns the id. Otherwise `react-router-dom` would block while its parent
`react-router` was allowed.

## Consequences

- The audit gate stays meaningful at high and critical rather than being
  lowered to critical, which would have silently dropped every future high.
- Each exception has to be written down with a reason, so the list is
  reviewable in a diff rather than invisible in a flag.
- The list needs pruning: drop `GHSA-qwww-vcr4-c8h2` once a fixed 7.x ships,
  otherwise a genuine RSC exposure could be masked if the app ever adopts RSC.

## Alternatives considered

- **`--audit-level=critical`.** One character to change, but it stops catching
  every future high advisory rather than this single known one.
- **Hold at 6.30.4.** Keeps the gate untouched while leaving two applicable
  open redirects in place, and blocks routine react-router maintenance
  indefinitely.
- **Pin 7.11.0**, below the vulnerable range. Avoids the high advisory but sits
  under 7.18.0, so it reinstates two of the three moderates.
