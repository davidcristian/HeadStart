# HeadStart — Full Codebase Audit (2026-07-02)

An exhaustive, read-only audit of the entire repository, graded against market best
practices and design patterns. This directory **documents** findings; it changes no
product code. Fixes are tracked here and shipped later as scoped PRs — exactly as the
first audit ([../docs/audit-backlog.md](../docs/audit-backlog.md)) was.

- **Audited commit:** `2630231` · **branch:** `docs/audit-2026-07` (off `master`)
- **Scope:** backend (FastAPI/Celery, ~38k LOC), frontend (React/Vite), Terraform/IaC,
  Docker, CI, docs — every tracked source file.
- **Method:** ~357 autonomous agents across 4 phases; every medium-and-up finding
  survived 3–5 independent adversarial verifiers. See [methodology.md](methodology.md).

## Headline

**269 tracked findings** (from 350 verified records, with near-duplicates and systemic
classes merged): **0 critical · 12 high · 71 medium · 186 low.** No critical issues, and
**no regressions** of the 77 items fixed in the first audit. The codebase is well-built —
clean layering, 100% test coverage, strict typing — so most findings are correctness
edge-cases and hardening/consistency gaps rather than structural problems.

Recurring themes worth fixing first:

1. **Auto-apply "false success" (WS23).** Several live-submit adapters (Apple, Microsoft,
   Indeed, Meta multipart, Workday) treat an HTTP 200 carrying an error/`success:false`
   body as a successful application — the exact WS4 Greenhouse fix left un-swept across
   siblings. Users believe they applied when they did not.
2. **Concurrency / double-send (WS17).** Pending recruiter replies and `enqueue_apply`
   read-then-write without a lease or unique constraint, so redelivery / overlapping ticks
   can double-send emails or double-submit applications — the WS2 pattern in new places.
3. **Account lifecycle & GDPR (WS15).** Account deletion never cancels the Stripe
   subscription and the data export omits most user-owned tables (applications, artifacts,
   inbox, deliveries) — an Art.17/Art.15 completeness gap.
4. **Resume/LaTeX pipeline (WS26/WS27).** `render_resume_template` escapes the very LaTeX
   markup the template requires (breaking compiles), and user/AI templates are compiled
   without `-no-shell-escape` or a `\input`/`\write18` scan.
5. **Secret & token hygiene (WS14).** Password-reset / email-verification tokens are logged
   in plaintext when SMTP is unconfigured, with no production guard.

## Start here

| If you want to…                                   | Open |
| ------------------------------------------------- | ---- |
| Track & tick off every finding (severity-ordered) | [backlog.md](backlog.md) |
| See best-practice grades per dimension            | [scorecard.md](scorecard.md) |
| Understand how the audit was run & verified        | [methodology.md](methodology.md) |
| Get full context on one finding (to fix it)        | [findings/](findings/) — one doc per area |

## Highest-priority findings (all high; no criticals)

| ID | Finding | Location |
| -- | ------- | -------- |
| [APL-01](findings/appliers.md#apl-01) | Apple `applyJob` reports *submitted* on a `{"success": false}` 200 body | `appliers/adapters/apple_careers_live.py:121` |
| [APL-02](findings/appliers.md#apl-02) | Indeed live Easy Apply never sends the session cookies it gates on | `appliers/adapters/indeed.py:124` |
| [APL-03](findings/appliers.md#apl-03) | Microsoft/Apple SmartApply report success on a 200 error body | `appliers/adapters/microsoft_careers.py:143` |
| [APL-04](findings/appliers.md#apl-04) | Required questionnaire answer silently dropped, bypassing the missing-required guard | `appliers/adapters/workday_questionnaire_answers.py:48` |
| [AIA-01](findings/ai-adapters.md#aia-01) | `render_resume_template` escapes structured LaTeX markup, breaking every resume compile | `resumes/template.py:31` |
| [AUT-01](findings/auth-security.md#aut-01) | Reset & verify tokens logged in plaintext when SMTP unset (no prod guard) | `core/email.py:88` |
| [AUT-02](findings/auth-security.md#aut-02) | Account deletion never cancels the Stripe subscription / customer | `services/auth_account.py:70` |
| [DAT-01](findings/data-model.md#dat-01) | Deleting the bootstrap admin resets the registration lock, auto-promoting the next registrant | `repositories/users.py:37` |
| [OPS-01](findings/devops.md#ops-01) | `deploy.sh` rolls task defs pinned to an image tag the build never re-pushes | `scripts/deploy.sh:33` |
| [XCT-01](findings/cross-cutting.md#xct-01) | Pending auto-reply queue has no lease; overlapping ticks double-send recruiter emails | `repositories/inbox_pending_replies.py:24` |
| [XCT-02](findings/cross-cutting.md#xct-02) | `enqueue_apply` read-then-write with no unique constraint double-submits live applications | `services/apply.py:49` |
| [XCT-03](findings/cross-cutting.md#xct-03) | `process_pending_replies` has no row lock; redelivery double-sends the SMTP reply | `services/pending_replies.py:133` |

## Findings by area

| Area | Doc | Findings (H/M/L) |
| ---- | --- | ---------------- |
| Appliers (auto-apply adapters) | [appliers.md](findings/appliers.md) | 20 (4/5/11) |
| Scrapers | [scrapers.md](findings/scrapers.md) | 6 (0/2/4) |
| Services — pipeline/alerts/digest | [services-pipeline.md](findings/services-pipeline.md) | 14 (0/6/8) |
| Billing / plans / promo / admin | [billing.md](findings/billing.md) | 11 (0/3/8) |
| Auth, crypto, core, config | [auth-security.md](findings/auth-security.md) | 24 (2/6/16) |
| API routers & schemas | [api-schemas.md](findings/api-schemas.md) | 12 (0/3/9) |
| Inbox — mail, OAuth, replies | [inbox.md](findings/inbox.md) | 16 (0/7/9) |
| AI adapters / resumes / LaTeX | [ai-adapters.md](findings/ai-adapters.md) | 15 (1/3/11) |
| Notifiers / worker / CLI | [notifiers-worker.md](findings/notifiers-worker.md) | 10 (0/3/7) |
| Curated portals | [portals.md](findings/portals.md) | 1 (0/0/1) |
| Data model / repos / migrations | [data-model.md](findings/data-model.md) | 16 (1/5/10) |
| Frontend (React, a11y, PWA) | [frontend.md](findings/frontend.md) | 39 (0/6/33) |
| DevOps — Terraform/Docker/CI | [devops.md](findings/devops.md) | 41 (1/11/29) |
| Documentation drift & licensing | [docs-drift.md](findings/docs-drift.md) | 18 (0/0/18) |
| Test quality | [test-quality.md](findings/test-quality.md) | 7 (0/1/6) |
| Cross-cutting (≥3 modules) | [cross-cutting.md](findings/cross-cutting.md) | 24 (3/11/10) |

## Best-practice scorecard (summary)

Solid **B+ overall**. Full justifications in [scorecard.md](scorecard.md).

| A- | B+ | B | B- | C+ |
| -- | -- | - | -- | -- |
| Architecture · API design | Security · Data layer · Testing · Frontend | Docs · Observability · Performance | CI/CD & IaC · Error-resilience | Dependency hygiene & licensing |

The strongest dimensions are architecture (clean layering + adapter registries) and API
design; the weakest is dependency hygiene & licensing — chiefly the absence of any
dependency/CVE scanning, plus unpinned dependency floors.

## How this was produced (TL;DR)

Discovery ran 28 subsystem deep-dives (each under two lenses) plus 18 whole-repo sweeps
(OWASP/ASVS, multi-user isolation, secrets/PII flow, GDPR, concurrency, performance,
dependency CVEs, IaC/AWS Well-Architected, CI/CD, accessibility, licensing, …), followed
by a gap-fill pass. Every finding was then re-checked by 3–5 independent refuters using
five distinct refutation angles; only strict-majority-confirmed findings survived (6 were
refuted outright and severity was recalibrated down where verifiers found inflation).
Coverage: **97% of non-test source** was read; the remainder is test files (audited for
quality by sampling) and reference data. Details, rubrics, the refuted-findings log, and
the full coverage manifest are in [methodology.md](methodology.md).
