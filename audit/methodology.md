# Audit Methodology & Appendix

How this audit was produced, so its findings can be trusted and reproduced. Audited commit: `2630231` (branch `docs/audit-2026-07`, off `master`).

## Process — 4 phases, ~357 autonomous agents

A deterministic orchestrator fanned out read-only subagents; all judgment is the agents', all mechanical steps (dedup, vote-tallying, median severity, ID assignment, rendering) are code.

| Phase | What ran | Agents |
| --- | --- | --- |
| 1 · Discovery | 28 deep-dives ×2 lenses + 18 whole-repo sweeps + gap-fill | 84 + 4 |
| 2 · Verification | 3–5 adversarial refuters per finding, majority vote | 211 |
| 3 · Calibration | severity panel + workstream clustering + 12-dim scorecard | 17 |
| 4 · Synthesis | one writer per area findings doc | 16 |

### Discovery
28 subsystem deep-dives (each run under 2 independent lenses — adversarial correctness/security and conventions/best-practice) plus 18 whole-repo cross-cutting sweeps (OWASP/ASVS, multi-user isolation, secrets/PII flow, GDPR, error handling, performance/N+1, concurrency, dependency CVEs, config drift, docs drift, test quality, API contracts, IaC/AWS Well-Architected, CI/CD, observability, accessibility, i18n, licensing). A gap-fill wave then covered source files the main wave did not open.

### Adversarial verification
Every finding was re-checked by independent refuters (3 per finding; **5** for every critical/high) using five distinct refutation angles — upstream-guards, tests-&-callers, factual-repro, severity-scrutiny, and steelman-then-attack. A finding survived only on a strict majority `confirmed` vote; refuted items were dropped (logged below). Final severity is the median of the original and all verifier-proposed severities, then a comparative calibration panel.

**Verification funnel:** 361 raw → 349 after exact-dedup → 355 confirmed (6 refuted / down-voted out) → **274 tracked** items after the writer stage merged near-duplicates and rolled up systemic classes.

## Severity & type rubric

- **🔴 critical** — unauth compromise, cross-tenant breach, secret disclosure at scale, RCE, or autonomous action acting destructively without consent.
- **🟠 high** — condition-gated authz bypass, single-tenant PII leak, real-impact injection, money-loss billing bug, data-loss migration.
- **🟡 medium** — precondition-heavy exploit, DoS, low-sensitivity info leak, recoverable incorrectness, tight-timing race.
- **⚪ low** — hardening/defense-in-depth, coverage-theater, consistency/style, doc drift.

Tie-break: PII/credential/money/code-exec code rounds up; config/preset data rounds down.

## Prior-audit regression check

Every agent read the 2026-07-01 first audit's 77 resolved items as both an exclusion list and a regression checklist. Result: **0 regression(s)** of resolved items and **100 finding(s) related-to** (distinct deltas near) prior items were surfaced; all other confirmed findings are new ground.

## Coverage manifest

- Auditable tracked files (excludes vendored/generated/binaries): **1253**
- Files opened by ≥1 agent: **785** (63% of auditable; **97% of non-test source**)
- Not individually opened: **468** — overwhelmingly test files (444; sampled by the test-quality sweep rather than each read), `__init__.py`, fixtures, and terraform `outputs.tf`/`variables.tf`. No production source module of consequence was left unread after gap-fill.

## Limitations

- Findings are static-analysis + code-reading judgments at one commit; they were not reproduced in a running environment. Each carries a confidence and a verifier vote count.
- Test files were audited for *quality* by sampling, not read exhaustively (coverage is already gated at 100%, so the goal was anti-coverage-theater, not more coverage).
- Dependency-CVE findings reflect advisories known at audit time against the pinned ranges.

## Refuted / down-voted findings (transparency log)

6 candidate findings were dropped by the verifiers. A sample of what was refuted and why (kept for auditability — these are NOT open issues):

| Candidate | Why refuted |
| --- | --- |
| JobApplyRequest cover_letter and tailored_resume_b64 have no max_length (`backend/app/schemas/job.py`) | Claim is false: decode_tailored_resume (tailored_resume.py:27-29) enforces profile_resume_max_bytes (2 MB) on the decoded bytes, so tailored_resume_b64 does NOT bypass that limit.  |
| generic_html fetch omits upfront assert_safe_outbound_url that playwright_html has (`backend/app/scrapers/adapters/generic_html.py`) | HttpClient.get_text (http.py:119) always calls assert_safe_outbound_url(url) before every request regardless of the event hook, so generic_html.fetch is already guarded; the missin |
| Service-worker NetworkOnly API rule matches only same-origin /api/ pathname (`frontend/vite.config.ts`) | Callers hardcode /api/v1/ in the path so pathname always starts with /api/ even cross-origin; navigateFallback applies only to navigation requests not fetch, and unmatched GETs pas |
| PendingDigest.add lacks IntegrityError guard on duplicate seen_job re-queue (`backend/app/repositories/digest.py`) | run_search is one session_scope transaction (max_retries=0); redelivery sees full commit or full rollback. If committed, _dedupe filters the external_id since seen_job exists, so _ |
| Floors permit fastapi/starlette/python-multipart versions with DoS CVEs (`backend/pyproject.toml`) | Floors only permit vulnerable versions, but pip resolves to the newest satisfying release, so the concrete scenario resolving fastapi 0.111 + starlette 0.37 + multipart 0.0.9 is fa |
| VerifyEmail effect re-runs on user change, re-POSTing the consumed token (`frontend/src/pages/VerifyEmailPage.tsx`) | majority of verifiers could not confirm |
