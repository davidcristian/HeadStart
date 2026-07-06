# Audit Backlog — Full Codebase Audit 2026-07-02

Living tracker for the **second** full-codebase audit (branch `docs/audit-2026-07`, commit `2630231`). Same tracker format as the 2026-07-01 first audit; workstream numbering **continues at WS14**. Update the Status column (and strike the row) when an item ships; link the PR. Full context for every item lives in the linked [findings/](findings/) doc.

Produced by a read-only multi-agent audit at commit `09957ec` — **every medium-and-up finding adversarially verified** by 3–5 independent refuters (majority vote). **269 tracked findings** from the original pass (0 critical · 12 high · 71 medium · 186 low), consolidated from 350 verified records (near-duplicates and systemic classes merged in the findings docs). This audit deliberately targeted ground the first audit did not cover — IaC/CI-CD security, accessibility, dependency CVEs, licensing, GDPR completeness, performance, observability — and swept the full *class* of every instance-fix the first audit made.

**Delta follow-up (2026-07-03).** A scoped re-audit of the fixes shipped since the baseline marked **APL-01** and **APL-02** ✅ done and **APL-03** 🔜 in progress (Microsoft closed; Apple residual [APL-28](findings/appliers.md#apl-28)), and re-confirmed **APL-04** still ☐ open. It also added **7 findings** (1 medium, 6 low) under **WS42**; the counts below include them (**281 tracked** total).

**Progress (2026-07-10).** **BIL-02 / BIL-03 fixed:** Stripe subscription `updated`/`deleted` webhooks ignore superseded subscription ids and events older than `user.stripe_billing_event_at`, and delete clears `stripe_subscription_id` — [PR](https://github.com/davidcristian/HeadStart/pull/38). **AUT-08 / XCT-21 fixed:** outbound httpx and Playwright connects use the IP from a single validated DNS lookup (Host + HTTPS `sni_hostname` preserved) so a rebinding resolver cannot reach private/metadata addresses after the SSRF check; telegram joins other notifiers on `pinned_request` — [PR](https://github.com/davidcristian/HeadStart/pull/37). **AUT-06 / XCT-20 fixed:** worker `:METRICS_PORT/metrics` now enforces the same optional `Authorization: Bearer` check as the API `/metrics` route (also closes DOC-22 doc drift) — [PR](https://github.com/davidcristian/HeadStart/pull/36). **XCT-16 fixed:** production `frontend/nginx.conf` emits CSP, `X-Frame-Options`, HSTS, `nosniff`, `Referrer-Policy`, and `Permissions-Policy` on the SPA HTML shell (also closes FRO-11) — [PR](https://github.com/davidcristian/HeadStart/pull/35). **BIL-01 fixed:** admin `update_user` emits structured `admin_event=user_update` logs (actor_id, target_id, before/after `is_active`/`is_admin`/`plan`) so privilege and plan mutations leave a server-side trail — [PR](https://github.com/davidcristian/HeadStart/pull/34). **AUT-26 fixed:** forgot-password always burns token generate+hash and queues SMTP on BackgroundTasks so response timing cannot enumerate accounts — [PR](https://github.com/davidcristian/HeadStart/pull/33). **AUT-10 fixed:** auth login/reset/logout/deletion emit structured `auth_event` logs (email HMAC + IP, no plaintext) and failed logins increment `headstart_auth_login_failures_total` — [PR](https://github.com/davidcristian/HeadStart/pull/32). **AUT-05 fixed:** credential Fernet keys are scrypt-stretched (legacy SHA-256 decrypt retained via MultiFernet), `CREDENTIALS_SECRET_KEY_PREVIOUS` enables rotation, and non-local boots require length ≥ 32 — [PR](https://github.com/davidcristian/HeadStart/pull/31). **AUT-03 fixed:** auth login/register/forgot/reset/verify/resend/refresh use process-local sliding-window rate limits (per IP / email / user) and return HTTP 429 when exceeded — [PR](https://github.com/davidcristian/HeadStart/pull/30). **XCT-09 / AUT-32 fixed:** GDPR `GET /auth/me/export` `format_version` 2 includes applications, artifacts, deliveries, mailbox metadata, inbox rows, promo redemptions, and resume/template bytes (also restores DOC-13/DOC-15 auth.md export wording) — [PR](https://github.com/davidcristian/HeadStart/pull/29). **FRO-06 fixed:** `/subprocessors` discloses Google Gemini, Anthropic, and Gmail / Outlook / Yahoo mailbox OAuth alongside AWS/Stripe/OpenAI/SMTP — [PR](https://github.com/davidcristian/HeadStart/pull/28). **FRO-05 fixed:** privacy policy discloses auto-apply transmission of application-profile PII to career sites, states lawful basis (consent for opt-in third-party sends), and each `application_log` attempt stamps an auditable `user_consent` record — [PR](https://github.com/davidcristian/HeadStart/pull/27). **FRO-04 fixed:** privacy policy discloses purpose-specific AI data categories (summaries, cover letters, resume curation, email classification, reply drafting) including profile PII and recruiter email content — [PR](https://github.com/davidcristian/HeadStart/pull/26). **DAT-02 / DAT-10 fixed:** account deletion redacts prior `data_request_log` export rows and writes only an HMAC email pseudonym (no IP/UA) for the deletion audit row so recoverable PII does not survive erasure — [PR](https://github.com/davidcristian/HeadStart/pull/25). **XCT-08 fixed:** admin deactivation bumps `token_version` so pre-lockout JWTs stay invalid after reactivation — [PR](https://github.com/davidcristian/HeadStart/pull/24). **XCT-06 / API-12 fixed:** `PlanFeaturesRead` includes `portal_search` so `/meta` no longer strips the Pro portal-search flag and the Portals UI can enable cross-portal search for entitled users — [PR](https://github.com/davidcristian/HeadStart/pull/23). **FRO-03 / XCT-17 fixed:** scraped job URLs go through `safeHref()` (http/https only) at Jobs, Applications, Search health, Profile history, and Portals results so `javascript:` hrefs cannot XSS the session — [PR](https://github.com/davidcristian/HeadStart/pull/22). **FRO-01 fixed:** `AuthProvider` clears the React Query cache on login, logout, and hard 401 so a shared-browser session switch cannot serve the previous user's cached PII — [PR](https://github.com/davidcristian/HeadStart/pull/21). **XCT-14 fixed:** hashed pip-tools lockfiles (`backend/requirements*.txt`) pin runtime/dev/playwright installs; Docker, CI, and `just setup` use `--require-hashes` (regenerate with `just lock-backend`) — [PR](https://github.com/davidcristian/HeadStart/pull/20). **XCT-13 fixed:** prefork Celery children that lose the `METRICS_PORT` race catch `EADDRINUSE`, log, and continue instead of crash-looping the pool — [PR](https://github.com/davidcristian/HeadStart/pull/19). **NTF-03 fixed:** Celery sets soft/hard time limits, `task_reject_on_worker_lost`, and `result_expires`; `apply_to_job` commits `queued`→`processing` before the employer POST so `acks_late` redelivery cannot double-submit (also closes NTF-13/NTF-14 config gaps) — [PR](https://github.com/davidcristian/HeadStart/pull/18). **XCT-12 fixed:** immediate `run_search` commits new `seen_job` rows before `notifier.send` so an `acks_late` redelivery after a mid-send crash dedupes instead of re-alerting the same jobs — [PR](https://github.com/davidcristian/HeadStart/pull/17). **XCT-11 fixed:** ghost detection claims stale applications under `FOR UPDATE SKIP LOCKED`, stamps `ghosted_at`, and commits the lease before SMTP so overlapping ticks / `acks_late` redelivery cannot double-send self-summaries; failed sends release the lease for retry — [PR](https://github.com/davidcristian/HeadStart/pull/16). **SVC-07 fixed:** pipeline scrape/notify and digest flush re-check `allows_scraper` / `allows_notifier` at consumption time so premium adapters stop after downgrade — [PR](https://github.com/davidcristian/HeadStart/pull/15). **SVC-06 fixed:** ghost-detection `process_due` isolates per-job failures (log + continue) and commits after each successful ghost so one bad mailbox/token cannot abort the batch or roll back earlier `ghosted_at` marks — [PR](https://github.com/davidcristian/HeadStart/pull/14). **SVC-04 / SVC-05 fixed:** digest `flush_due` isolates per-search notifier failures (log + continue) and commits after each successful flush so one bad target cannot block other digests or roll back already-delivered bookkeeping — [PR](https://github.com/davidcristian/HeadStart/pull/13). **SVC-02 / SVC-08 fixed:** pipeline auto-apply now enforces per-plan `max_auto_applies_per_day` (rolling 24h live `application_log` count) before queueing from `run_search`, so opt-in sources cannot fan out unbounded live applications — [PR](https://github.com/davidcristian/HeadStart/pull/12). **Progress (2026-07-09).** **XCT-02 / SVC-01 fixed (tracker):** live-apply double-submit was already guarded by partial unique index `uq_application_log_inflight_job` + `try_add_pending` (`334164a`); audit tracker/findings/docs aligned — [PR](https://github.com/davidcristian/HeadStart/pull/11). **XCT-01 / XCT-03 fixed:** pending auto-reply queue now leases due rows (`pending` → `sending` under `FOR UPDATE SKIP LOCKED`), commits the lease, then SMTP-sends — overlapping ticks / `acks_late` redelivery can no longer double-send recruiter replies — [PR](https://github.com/davidcristian/HeadStart/pull/10). **OPS-01 fixed:** `deploy.sh` registers ECS task-definition revisions pinned to the just-pushed `IMAGE_TAG` (via `app.cli.ecs_task_def`) before rolling services, so deploys no longer force-new-deployment against a Terraform `latest` pin the build never re-pushes — [PR](https://github.com/davidcristian/HeadStart/pull/9). **DAT-01 fixed:** `registration_lock.bootstrap_claimed` permanently latches bootstrap admin promotion so deleting the bootstrap admin cannot re-open self-service admin creation — [PR](https://github.com/davidcristian/HeadStart/pull/8). **AUT-02 fixed:** account deletion cancels the Stripe subscription and deletes the Stripe customer (best-effort) before removing the local user row — [PR](https://github.com/davidcristian/HeadStart/pull/7). **AUT-01 fixed:** non-local boots require `SMTP_HOST`; `_send_or_log_email` refuses to log reset/verify token URLs outside `local`/`test` — [PR](https://github.com/davidcristian/HeadStart/pull/6). **APL-04 fixed:** Workday `build_questionnaire_answers` now flags required questions whose present value cannot convert (choice/numeric) — [PR](https://github.com/davidcristian/HeadStart/pull/5). Closes 1 more of the remaining highs (merged APL-10). **Earlier same day — WS26 fixed:** AIA-01 (the high-severity LaTeX-escape bug that broke every default-template and AI-curated resume) plus its WS26 companions AIA-12/AIA-16/AIA-17. Renderer now treats `experience` as controlled LaTeX and escapes only free-text/PII scalars; the heuristic path escapes its own free text; PDF-name derivation, the `import json` placement, and `_validate_pdf` settings injection are corrected. Full gate green (ruff/black/mypy, 3109 backend tests, 100% coverage). This closes 1 of the 12 highs (11 open) and 3 lows. Shipping WS26 also surfaced a pre-commit/CI formatter-pin drift that reformat-looped on clean files; fixed and recorded as **OPS-69** (WS37, new — brings the tally to 282 tracked).

**Status legend:** ☐ open · 🔜 in progress · ✅ done
**Type:** 🐞 bug · 🔒 security · 📝 doc · 🧪 test · ♻️ refactor · 🔁 consistency · ⚡ perf
**Severity:** 🔴 CRIT · 🟠 HIGH · 🟡 MED · ⚪ LOW

**By severity:** 🔴 0 · 🟠 12 · 🟡 73 · ⚪ 197
**By type:** 🐞 93 · 🔒 94 · 📝 31 · 🧪 10 · ♻️ 8 · 🔁 31 · ⚡ 15

---

## At a glance — highest priority

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟠 HIGH | 🐞 | [AIA-01](findings/ai-adapters.md#aia-01) render_resume_template escapes structured LaTeX markup, breaking every default-template and AI-curated resume | `backend/app/resumes/template.py:31` | ✅ |
| 🟠 HIGH | 🐞 | [APL-01](findings/appliers.md#apl-01) Apple applyJob reports submitted on {"success": false} 200 body despite modeling it | `backend/app/appliers/adapters/apple_careers_live.py:121` | ✅ |
| 🟠 HIGH | 🐞 | [APL-02](findings/appliers.md#apl-02) Indeed live Easy Apply submit never sends the session cookies it gates on | `backend/app/appliers/adapters/indeed.py:124` | ✅ |
| 🟠 HIGH | 🐞 | [APL-03](findings/appliers.md#apl-03) Microsoft/Apple SmartApply submits report success on 200 error body (no post-2xx check) | `backend/app/appliers/adapters/microsoft_careers.py:143` | 🔜 |
| 🟠 HIGH | 🐞 | [APL-04](findings/appliers.md#apl-04) Required questionnaire answer silently dropped when value present but unresolvable | `backend/app/appliers/adapters/workday_questionnaire_answers.py:48` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/5) |
| 🟠 HIGH | 🔒 | [AUT-01](findings/auth-security.md#aut-01) Reset & verify tokens logged in plaintext when SMTP unset (no prod guard) | `backend/app/core/email.py:88` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/6) |
| 🟠 HIGH | 🐞 | [AUT-02](findings/auth-security.md#aut-02) Account deletion never cancels Stripe subscription or deletes Stripe customer | `backend/app/services/auth_account.py:70` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/7) |
| 🟠 HIGH | 🔒 | [DAT-01](findings/data-model.md#dat-01) Deleting bootstrap admin resets registration lock, auto-promoting next registrant to admin | `backend/app/repositories/users.py:37` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/8) |
| 🟠 HIGH | 🐞 | [OPS-01](findings/devops.md#ops-01) deploy.sh redeploys task defs pinned to a tag never re-pushed by the build | `scripts/deploy.sh:33` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/9) |
| 🟠 HIGH | 🐞 | [XCT-01](findings/cross-cutting.md#xct-01) Pending auto-reply queue has no lease; overlapping ticks double-send recruiter emails | `backend/app/repositories/inbox_pending_replies.py:24` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/10) |
| 🟠 HIGH | 🐞 | [XCT-02](findings/cross-cutting.md#xct-02) enqueue_apply read-then-write with no unique constraint double-submits live applications | `backend/app/services/apply.py:49` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/11) |
| 🟠 HIGH | 🐞 | [XCT-03](findings/cross-cutting.md#xct-03) process_pending_replies has no row lock; redelivery double-sends recruiter SMTP reply | `backend/app/services/pending_replies.py:133` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/10) |

---

## WS14 — Concurrency & before-commit correctness in worker pipelines
_11 item(s): 3 high, 8 medium._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟠 HIGH | 🐞 | [XCT-01](findings/cross-cutting.md#xct-01) Pending auto-reply queue has no lease; overlapping ticks double-send recruiter emails | `backend/app/repositories/inbox_pending_replies.py:24` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/10) |
| 🟠 HIGH | 🐞 | [XCT-02](findings/cross-cutting.md#xct-02) enqueue_apply read-then-write with no unique constraint double-submits live applications | `backend/app/services/apply.py:49` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/11) |
| 🟠 HIGH | 🐞 | [XCT-03](findings/cross-cutting.md#xct-03) process_pending_replies has no row lock; redelivery double-sends recruiter SMTP reply | `backend/app/services/pending_replies.py:133` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/10) |
| 🟡 MED | 🐞 | [SVC-01](findings/services-pipeline.md#svc-01) Live-apply double-submit guard is non-atomic, no unique constraint or lock | `backend/app/services/apply.py:49` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/11) |
| 🟡 MED | 🐞 | [SVC-02](findings/services-pipeline.md#svc-02) Auto-apply has no per-plan or volume cap once a source opts in | `backend/app/services/apply.py:62` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/12) |
| 🟡 MED | 🐞 | [SVC-04](findings/services-pipeline.md#svc-04) Digest flush tick has no per-search exception isolation | `backend/app/services/digest.py:64` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/13) |
| 🟡 MED | 🐞 | [SVC-05](findings/services-pipeline.md#svc-05) Digest flush sends before commit; a later search failure re-sends earlier digests | `backend/app/services/digest.py:57` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/13) |
| 🟡 MED | 🐞 | [SVC-06](findings/services-pipeline.md#svc-06) Ghost-detection loop lacks per-item exception isolation vs orchestration | `backend/app/services/ghost_detection.py:51` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/14) |
| 🟡 MED | 🔒 | [SVC-07](findings/services-pipeline.md#svc-07) Premium scraper/notifier gates not re-checked at pipeline run (survive downgrade) | `backend/app/services/pipeline.py:105` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/15) |
| 🟡 MED | 🐞 | [XCT-11](findings/cross-cutting.md#xct-11) detect_ghosted_applications unlocked, sets ghosted_at after send; overlap double-emails | `backend/app/services/ghost_detection.py:76` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/16) |
| 🟡 MED | 🐞 | [XCT-12](findings/cross-cutting.md#xct-12) run_search notifies before commit; acks-late redelivery re-notifies same jobs | `backend/app/services/pipeline.py:118` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/17) |

## WS15 — Celery worker reliability & dependency pinning
_7 item(s): 3 medium, 4 low._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🐞 | [NTF-03](findings/notifiers-worker.md#ntf-03) acks_late set but no task time limit / reject-on-worker-lost; non-idempotent live apply can double-submit | `backend/app/worker/celery_app.py:19` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/18) |
| 🟡 MED | 🐞 | [XCT-13](findings/cross-cutting.md#xct-13) Every prefork worker child binds the same metrics port -> EADDRINUSE crash loop | `backend/app/worker/celery_app.py:33` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/19) |
| 🟡 MED | 🔒 | [XCT-14](findings/cross-cutting.md#xct-14) Backend deps all floating >= floors, no lockfile: non-reproducible builds | `backend/pyproject.toml:10` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/20) |
| ⚪ LOW | 🐞 | [NTF-13](findings/notifiers-worker.md#ntf-13) No task_time_limit; a hung Playwright scrape holds a worker slot indefinitely | `backend/app/worker/celery_app.py:19` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/18) |
| ⚪ LOW | ⚡ | [NTF-14](findings/notifiers-worker.md#ntf-14) Result backend enabled with no result_expires; unread task results accumulate in Redis | `backend/app/worker/celery_app.py:16` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/18) |
| ⚪ LOW | ♻️ | [XCT-22](findings/cross-cutting.md#xct-22) selectolax native C-ext on untrusted-HTML path: bus-factor / unpinned | `backend/pyproject.toml:23` | ☐ |
| ⚪ LOW | 🔁 | [XCT-23](findings/cross-cutting.md#xct-23) Manifest floors lag installed majors, hiding real support contract | `backend/pyproject.toml:20` | ☐ |

## WS16 — Frontend security: URL-scheme XSS & session cache leak
_3 item(s): 3 medium._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🔒 | [FRO-01](findings/frontend.md#fro-01) Logout/login never clear React Query cache; previous user's PII survives into next session | `frontend/src/auth/AuthContext.tsx:31` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/21) |
| 🟡 MED | 🔒 | [FRO-03](findings/frontend.md#fro-03) Scraped job URLs rendered into href with no scheme allow-list (javascript: XSS) | `frontend/src/components/JobList.tsx:134` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/22) |
| 🟡 MED | 🔒 | [XCT-17](findings/cross-cutting.md#xct-17) Scraped, unvalidated job URLs rendered into href enable javascript:-scheme XSS | `frontend/src/components/JobList.tsx:134` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/22) |

## WS17 — portal_search plan flag & admin token-version
_3 item(s): 2 medium, 1 low._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🐞 | [XCT-06](findings/cross-cutting.md#xct-06) PlanFeaturesRead omits portal_search; /meta strips it and Pro portal search is gated off for all | `backend/app/schemas/plan.py:22` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/23) |
| 🟡 MED | 🔒 | [XCT-08](findings/cross-cutting.md#xct-08) Admin deactivate then reactivate resurrects pre-deactivation tokens (no version bump) | `backend/app/services/admin.py:41` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/24) |
| ⚪ LOW | 🔁 | [API-12](findings/api-schemas.md#api-12) PlanFeaturesRead omits portal_search though snapshot() emits it | `backend/app/schemas/plan.py:22` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/23) |

## WS18 — GDPR: account deletion, data export completeness & retention
_15 item(s): 2 high, 5 medium, 8 low._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟠 HIGH | 🔒 | [AUT-01](findings/auth-security.md#aut-01) Reset & verify tokens logged in plaintext when SMTP unset (no prod guard) | `backend/app/core/email.py:88` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/6) |
| 🟠 HIGH | 🐞 | [AUT-02](findings/auth-security.md#aut-02) Account deletion never cancels Stripe subscription or deletes Stripe customer | `backend/app/services/auth_account.py:70` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/7) |
| 🟡 MED | 🔒 | [DAT-02](findings/data-model.md#dat-02) DataRequestLog retains user_email & IP indefinitely after account erasure | `backend/app/models/data_request_log.py:22` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/25) |
| 🟡 MED | 📝 | [FRO-04](findings/frontend.md#fro-04) Privacy policy understates AI data: resume/profile PII and recruiter emails sent | `frontend/src/pages/PrivacyPolicyPage.tsx:78` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/26) |
| 🟡 MED | 📝 | [FRO-05](findings/frontend.md#fro-05) No lawful-basis/consent record for auto-apply sending PII to job boards | `frontend/src/pages/PrivacyPolicyPage.tsx:60` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/27) |
| 🟡 MED | 📝 | [FRO-06](findings/frontend.md#fro-06) Subprocessor list omits shipped Gemini/Anthropic AI and mailbox providers | `frontend/src/pages/SubprocessorsPage.tsx:8` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/28) |
| 🟡 MED | 🐞 | [XCT-09](findings/cross-cutting.md#xct-09) Data export omits most user-owned tables (applications, artifacts, inbox, delivery, resume bytes, promos) | `backend/app/services/auth_account.py:45` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/29) |
| ⚪ LOW | 🐞 | [AUT-32](findings/auth-security.md#aut-32) GDPR data export omits several user-owned entities (inbox, applications, portals) | `backend/app/services/auth_account.py:45` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/29) |
| ⚪ LOW | 🔒 | [AUT-33](findings/auth-security.md#aut-33) Deletion destroys but never revokes mailbox OAuth tokens at providers | `backend/app/services/auth_account.py:93` | ☐ |
| ⚪ LOW | ⚡ | [AUT-34](findings/auth-security.md#aut-34) GDPR data export loads every SeenJob with limit=None into memory in one request | `backend/app/services/auth_account.py:56` | ☐ |
| ⚪ LOW | 🔒 | [DAT-10](findings/data-model.md#dat-10) DataRequestLog retains user_email & IP indefinitely after account erasure (erasure-path view) | `backend/app/models/data_request_log.py:22` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/25) |
| ⚪ LOW | 🔒 | [DAT-18](findings/data-model.md#dat-18) Reset/verify token single-use relies only on post-use deletion, no consumed marker | `backend/app/repositories/password_reset_tokens.py:22` | ☐ |
| ⚪ LOW | 📝 | [DOC-13](findings/docs-drift.md#doc-13) auth.md data-export sentence corrupted: dangling paren, dropped endpoint + list | `docs/modules/auth.md:138` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/29) |
| ⚪ LOW | 📝 | [DOC-15](findings/docs-drift.md#doc-15) auth.md "everything they own" export omits apply logs, artifacts, inbox data | `docs/modules/auth.md:138` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/29) |
| ⚪ LOW | 📝 | [FRO-40](findings/frontend.md#fro-40) Retention section omits post-deletion audit-email retention and inbox data | `frontend/src/pages/PrivacyPolicyPage.tsx:120` | ☐ |

## WS19 — Auth hardening: rate-limit, audit logging, enumeration, JWT & crypto
_16 item(s): 1 high, 5 medium, 10 low._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟠 HIGH | 🔒 | [DAT-01](findings/data-model.md#dat-01) Deleting bootstrap admin resets registration lock, auto-promoting next registrant to admin | `backend/app/repositories/users.py:37` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/8) |
| 🟡 MED | 🔒 | [AUT-03](findings/auth-security.md#aut-03) No rate limiting on auth endpoints (login / register / forgot-password / reset / verify / resend) | `backend/app/api/v1/auth.py:64` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/30) |
| 🟡 MED | 🔒 | [AUT-05](findings/auth-security.md#aut-05) Fernet key: unsalted single SHA-256 derivation, no KDF, no key-rotation path | `backend/app/core/crypto.py:22` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/31) |
| 🟡 MED | 🔒 | [AUT-10](findings/auth-security.md#aut-10) Auth security events (login, failed login, reset, deletion) are never logged | `backend/app/services/auth.py:74` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/32) |
| 🟡 MED | 🔒 | [AUT-26](findings/auth-security.md#aut-26) forgot-password leaks account existence via timing (early return vs synchronous SMTP) | `backend/app/services/auth.py:113` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/33) |
| 🟡 MED | 🔒 | [BIL-01](findings/billing.md#bil-01) Admin user mutations (deactivate, grant admin, plan change) write no audit record | `backend/app/services/admin.py:26` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/34) |
| ⚪ LOW | 🔒 | [AUT-13](findings/auth-security.md#aut-13) No prod validator couples AUTH_COOKIE_SECURE/SameSite to FRONTEND_BASE_URL scheme | `backend/app/core/config.py:249` | ☐ |
| ⚪ LOW | ♻️ | [AUT-15](findings/auth-security.md#aut-15) No request/correlation ID in logs; log lines cannot be tied to a request or user | `backend/app/core/logging.py:18` | ☐ |
| ⚪ LOW | ♻️ | [AUT-16](findings/auth-security.md#aut-16) Logs are unstructured plaintext, not JSON; not machine-parseable for alerting | `backend/app/core/logging.py:19` | ☐ |
| ⚪ LOW | 🔒 | [AUT-17](findings/auth-security.md#aut-17) GDPR/audit client IP taken from unverified, unbounded X-Forwarded-For (spoofable) | `backend/app/core/request_meta.py:18` | ☐ |
| ⚪ LOW | 🔒 | [AUT-21](findings/auth-security.md#aut-21) JWT decode paths do not require exp/iat (RFC 8725) — accept unexpiring tokens | `backend/app/core/security.py:110` | ☐ |
| ⚪ LOW | 🔒 | [AUT-22](findings/auth-security.md#aut-22) RSS feed JWT is a 10-year bearer credential passed in the URL | `backend/app/core/security.py:58` | ☐ |
| ⚪ LOW | 🔒 | [AUT-27](findings/auth-security.md#aut-27) Registration returns 409 for existing email, confirming registered addresses | `backend/app/services/auth.py:59` | ☐ |
| ⚪ LOW | 🐞 | [AUT-28](findings/auth-security.md#aut-28) Concurrent duplicate registration surfaces IntegrityError as 500 not 409 | `backend/app/services/auth.py:59` | ☐ |
| ⚪ LOW | 🐞 | [AUT-30](findings/auth-security.md#aut-30) reset/verify leave token row unconsumed when user inactive/missing | `backend/app/services/auth.py:141` | ☐ |
| ⚪ LOW | 🔁 | [AUT-31](findings/auth-security.md#aut-31) Email-verification tokens hashed via hash_password_reset_token (naming drift) | `backend/app/services/auth.py:153` | ☐ |

## WS20 — HTTP security response headers & static-serving hardening
_8 item(s): 1 medium, 7 low._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🔒 | [XCT-16](findings/cross-cutting.md#xct-16) SPA served with no CSP, X-Frame-Options, HSTS, X-Content-Type-Options or Referrer-Policy | `frontend/nginx.conf:1` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/35) |
| ⚪ LOW | 🔒 | [AUT-23](findings/auth-security.md#aut-23) No security response headers (HSTS, nosniff, X-Frame-Options, Referrer-Policy) anywhere | `backend/app/main.py:28` | ☐ |
| ⚪ LOW | 🔒 | [AUT-25](findings/auth-security.md#aut-25) Swagger /docs, /redoc and /openapi.json exposed publicly in prod | `backend/app/main.py:22` | ☐ |
| ⚪ LOW | 🔒 | [FRO-08](findings/frontend.md#fro-08) Frontend nginx container runs as root (no USER directive) | `frontend/Dockerfile:15` | ☐ |
| ⚪ LOW | 🐞 | [FRO-10](findings/frontend.md#fro-10) index.html served with no Cache-Control while assets are immutable | `frontend/nginx.conf:19` | ☐ |
| ⚪ LOW | 🔒 | [FRO-11](findings/frontend.md#fro-11) nginx serves SPA without any security response headers | `frontend/nginx.conf:1` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/35) |
| ⚪ LOW | 🔒 | [FRO-12](findings/frontend.md#fro-12) vite-plugin-pwa/vite chain locks esbuild 0.21.5 (dev-server SSRF) | `frontend/package.json:39` | ☐ |
| ⚪ LOW | 🔒 | [FRO-20](findings/frontend.md#fro-20) Partner-ad iframe sandbox allows both allow-scripts and allow-same-origin | `frontend/src/components/FreeTierAd.tsx:51` | ☐ |

## WS21 — Metrics auth & SSRF DNS-rebinding
_6 item(s): 2 medium, 4 low._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🔒 | [AUT-06](findings/auth-security.md#aut-06) Worker /metrics HTTP server exposes Prometheus data unauthenticated on all interfaces | `backend/app/core/metrics.py:102` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/36) |
| 🟡 MED | 🔒 | [AUT-08](findings/auth-security.md#aut-08) SSRF guard resolves DNS then lets httpx re-resolve — DNS-rebinding TOCTOU bypass | `backend/app/core/outbound_url.py:55` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/37) |
| ⚪ LOW | 📝 | [DOC-22](findings/docs-drift.md#doc-22) metrics.md implies METRICS_TOKEN guards /metrics, but worker :9090 has no auth | `docs/modules/metrics.md:54` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/36) |
| ⚪ LOW | 🔒 | [OPS-54](findings/devops.md#ops-54) METRICS_TOKEN never set by Terraform; /metrics unauthenticated on prod tasks | `devops/terraform/modules/stack/main.tf:150` | ☐ |
| ⚪ LOW | 🔒 | [XCT-20](findings/cross-cutting.md#xct-20) Worker /metrics HTTP server ignores metrics_token — unauthenticated even when set | `backend/app/core/metrics.py:102` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/36) |
| ⚪ LOW | 🔒 | [XCT-21](findings/cross-cutting.md#xct-21) SSRF guard resolves DNS once; httpx re-resolves at connect (rebinding) | `backend/app/core/outbound_url.py:56` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/37) |

## WS22 — Billing webhook idempotency, promo throttling & plan sync
_11 item(s): 2 medium, 9 low._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🐞 | [BIL-02](findings/billing.md#bil-02) subscription.updated applied unconditionally; stale/out-of-order event re-grants plan | `backend/app/services/billing.py:202` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/38) |
| 🟡 MED | 🐞 | [BIL-03](findings/billing.md#bil-03) Subscription webhook applies stale/out-of-order events (deleted for old sub wipes plan) | `backend/app/services/billing.py:218` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/38) |
| ⚪ LOW | 🐞 | [BIL-04](findings/billing.md#bil-04) GET /admin/data-requests `limit` has no lower bound; negative reaches SQL LIMIT | `backend/app/api/v1/admin.py:47` | ☐ |
| ⚪ LOW | 🔒 | [BIL-06](findings/billing.md#bil-06) scraper_allowed defaults unknown adapters to allowed on every plan (fail-open) | `backend/app/core/plans.py:112` | ☐ |
| ⚪ LOW | 📝 | [BIL-07](findings/billing.md#bil-07) plans.py comment says 'Pro unlocks the rest' but premium scrapers are Plus+ | `backend/app/core/plans.py:16` | ☐ |
| ⚪ LOW | 🐞 | [BIL-08](findings/billing.md#bil-08) Admin plan change ignores active Stripe subscription; webhook overwrites it | `backend/app/services/admin.py:38` | ☐ |
| ⚪ LOW | 🔒 | [BIL-09](findings/billing.md#bil-09) Promo brute-force rate limit bypassed via /billing/checkout (resolve_for_checkout unthrottled) | `backend/app/services/promo_codes.py:108` | ☐ |
| ⚪ LOW | 🐞 | [BIL-10](findings/billing.md#bil-10) Free-trial gate keys on requested plan, not the plan_upgrade target billed | `backend/app/services/billing.py:121` | ☐ |
| ⚪ LOW | ♻️ | [BIL-11](findings/billing.md#bil-11) snapshot() plan field uses a no-op ternary (both branches identical) | `backend/app/services/plan_limits.py:68` | ☐ |
| ⚪ LOW | 🐞 | [BIL-13](findings/billing.md#bil-13) Stripe PromotionCode metadata promo_code_id always empty (set before flush) | `backend/app/services/promo_codes.py:245` | ☐ |
| ⚪ LOW | 🧪 | [TST-05](findings/test-quality.md#tst-05) Stripe-webhook 'unknown user is noop' tests assert nothing, cannot catch a regression | `backend/tests/services/test_billing_part2.py:161` | ☐ |

## WS23 — Apply adapters: post-2xx error-body & session cookies
_9 item(s): 3 high, 2 medium, 4 low._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟠 HIGH | 🐞 | [APL-01](findings/appliers.md#apl-01) Apple applyJob reports submitted on {"success": false} 200 body despite modeling it | `backend/app/appliers/adapters/apple_careers_live.py:121` | ✅ |
| 🟠 HIGH | 🐞 | [APL-02](findings/appliers.md#apl-02) Indeed live Easy Apply submit never sends the session cookies it gates on | `backend/app/appliers/adapters/indeed.py:124` | ✅ |
| 🟠 HIGH | 🐞 | [APL-03](findings/appliers.md#apl-03) Microsoft/Apple SmartApply submits report success on 200 error body (no post-2xx check) | `backend/app/appliers/adapters/microsoft_careers.py:143` | 🔜 |
| 🟡 MED | 🐞 | [APL-05](findings/appliers.md#apl-05) Meta resume (multipart) submit skips the GraphQL errors check the JSON path enforces | `backend/app/appliers/adapters/meta_careers_graphql.py:92` | ☐ |
| 🟡 MED | 🐞 | [APL-11](findings/appliers.md#apl-11) Workday name POST and terms PUT skip the post-2xx errorCode check sibling steps enforce | `backend/app/appliers/adapters/workday_submit.py:84` | ☐ |
| ⚪ LOW | 🔁 | [APL-16](findings/appliers.md#apl-16) Indeed & LinkedIn-hosted live submit skip the post-2xx error-body check siblings enforce | `backend/app/appliers/adapters/indeed.py:132` | ☐ |
| ⚪ LOW | 🐞 | [APL-20](findings/appliers.md#apl-20) Microsoft CSRF fetch swallows all exceptions via bare except Exception | `backend/app/appliers/adapters/microsoft_careers_common.py:90` | ☐ |
| ⚪ LOW | 🐞 | [APL-26](findings/appliers.md#apl-26) Live submit failure mid-flow leaves a partial, unfinalized application on the ATS | `backend/app/appliers/adapters/workday_submit.py:118` | ☐ |
| ⚪ LOW | 🧪 | [TST-02](findings/test-quality.md#tst-02) Indeed hosted-submit test asserts body but never that the session cookies are sent | `backend/tests/appliers/test_indeed.py:196` | ☐ |

## WS24 — Apply adapters: questionnaire/lookup/payload accuracy & dry-run default
_10 item(s): 1 high, 3 medium, 6 low._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟠 HIGH | 🐞 | [APL-04](findings/appliers.md#apl-04) Required questionnaire answer silently dropped when value present but unresolvable | `backend/app/appliers/adapters/workday_questionnaire_answers.py:48` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/5) |
| 🟡 MED | 🐞 | [APL-06](findings/appliers.md#apl-06) Meta education parallel arrays desync via per-column filters | `backend/app/appliers/adapters/meta_careers_payload.py:53` | ☐ |
| 🟡 MED | 🐞 | [APL-08](findings/appliers.md#apl-08) Workday lookup prefix/substring fallback silently submits wrong degree/field/skill WID | `backend/app/appliers/adapters/workday_lookup.py:61` | ☐ |
| 🟡 MED | 🐞 | [APL-13](findings/appliers.md#apl-13) flatten_lever_form_fields emits resume_file meta as dict-repr on live Lever submit | `backend/app/appliers/resume.py:59` | ☐ |
| ⚪ LOW | 🐞 | [APL-15](findings/appliers.md#apl-15) Apple questionnaireAnswers dumps profile.answers verbatim, not mapped to question ids | `backend/app/appliers/adapters/apple_careers_live.py:54` | ☐ |
| ⚪ LOW | 🔒 | [APL-21](findings/appliers.md#apl-21) Uber dry-run payload embeds live session_token, persisted to ApplicationLog | `backend/app/appliers/adapters/uber_careers_payload.py:110` | ☐ |
| ⚪ LOW | 🐞 | [APL-22](findings/appliers.md#apl-22) request_headers lets stored credential headers overwrite CSRF/Content-Type/Referer | `backend/app/appliers/adapters/workday_common.py:145` | ☐ |
| ⚪ LOW | 🐞 | [APL-23](findings/appliers.md#apl-23) Multi-choice questionnaire answer silently submits only resolvable selections | `backend/app/appliers/adapters/workday_questionnaire_answers.py:126` | ☐ |
| ⚪ LOW | 🐞 | [APL-24](findings/appliers.md#apl-24) Any 32-hex value trusted as a valid answer/lookup id without membership check | `backend/app/appliers/adapters/workday_questionnaire_answers.py:137` | ☐ |
| ⚪ LOW | 🐞 | [APL-27](findings/appliers.md#apl-27) ApplyContext.dry_run defaults to False (live submit by default) | `backend/app/appliers/types.py:22` | ☐ |

## WS25 — LinkedIn/Indeed ToS/CFAA disclosure & resume-upload
_6 item(s): 6 low._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| ⚪ LOW | 🔒 | [APL-17](findings/appliers.md#apl-17) LinkedIn/Indeed live apply hits private APIs with user cookies; no ToS/ban warning | `backend/app/appliers/adapters/linkedin.py:211` | ☐ |
| ⚪ LOW | 🔒 | [APL-19](findings/appliers.md#apl-19) LinkedIn resume upload forwards session cookies to a response-supplied URL | `backend/app/appliers/adapters/linkedin_resume_upload.py:37` | ☐ |
| ⚪ LOW | 📝 | [DOC-03](findings/docs-drift.md#doc-03) launch-checklist: LinkedIn/Indeed resume upload "not automated" contradicts code | `docs/launch-checklist.md:109` | ☐ |
| ⚪ LOW | 📝 | [DOC-05](findings/docs-drift.md#doc-05) launch-checklist supported-adapters list omits 4 registered appliers | `docs/launch-checklist.md:90` | ☐ |
| ⚪ LOW | 📝 | [DOC-12](findings/docs-drift.md#doc-12) No ToS/legal-risk disclosure for LinkedIn Voyager & Indeed smartapply automation | `docs/modules/appliers.md:607` | ☐ |
| ⚪ LOW | 🔒 | [XCT-19](findings/cross-cutting.md#xct-19) LinkedIn/Indeed credentialed scrape + auto-apply is under-disclosed ToS/CFAA risk | `backend/app/appliers/adapters/linkedin_common.py:9` | ☐ |

## WS26 — Resume template rendering LaTeX-escape bug ✅
_4 item(s): 1 high, 3 low. **Fixed** 2026-07-09 (gate green)._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟠 HIGH | 🐞 | [AIA-01](findings/ai-adapters.md#aia-01) render_resume_template escapes structured LaTeX markup, breaking every default-template and AI-curated resume | `backend/app/resumes/template.py:31` | ✅ |
| ⚪ LOW | 🐞 | [AIA-12](findings/ai-adapters.md#aia-12) PDF name via replace('.tex','.pdf') replaces every occurrence, mis-deriving output | `backend/app/resumes/compile.py:109` | ✅ |
| ⚪ LOW | 🔁 | [AIA-16](findings/ai-adapters.md#aia-16) profiles._encode/_decode use function-local `import json`, breaking module convention | `backend/app/services/profiles.py:239` | ✅ |
| ⚪ LOW | 🔁 | [AIA-17](findings/ai-adapters.md#aia-17) _validate_pdf reads module `default_settings`, not injected `self._settings`, for the size cap | `backend/app/services/resumes.py:163` | ✅ |

## WS27 — LaTeX compile sandboxing & template-bundle input scan
_6 item(s): 3 medium, 3 low._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🔒 | [AIA-03](findings/ai-adapters.md#aia-03) User LaTeX template compiled without -no-shell-escape and without an openin/sandbox restriction | `backend/app/resumes/compile.py:84` | ☐ |
| 🟡 MED | 🔒 | [AIA-06](findings/ai-adapters.md#aia-06) Bundle .tex content passed to compiler verbatim allows \input of absolute server paths | `backend/app/resumes/template_bundle.py:59` | ☐ |
| 🟡 MED | 🔒 | [AIA-07](findings/ai-adapters.md#aia-07) Template upload never scans .tex for \input / \write18 / \openin primitives | `backend/app/resumes/template_bundle.py:82` | ☐ |
| ⚪ LOW | 🔒 | [AIA-10](findings/ai-adapters.md#aia-10) LaTeX subprocess has a wall-clock timeout but no CPU / memory / process limits | `backend/app/resumes/compile.py:84` | ☐ |
| ⚪ LOW | 🔒 | [AIA-11](findings/ai-adapters.md#aia-11) LaTeX subprocess inherits the full parent environment, exposing secrets to the compiler | `backend/app/resumes/compile.py:84` | ☐ |
| ⚪ LOW | 🧪 | [TST-06](findings/test-quality.md#tst-06) Resume tests mock every compile/render path; render→compile contract untested | `backend/tests/services/test_resumes.py:86` | ☐ |

## WS28 — AI prompt-injection, PII exposure & outbound SSRF guard
_7 item(s): 1 medium, 6 low._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🔒 | [XCT-05](findings/cross-cutting.md#xct-05) Single stored AI key sent to whichever provider a purpose resolves to | `backend/app/ai/runtime_settings.py:111` | ☐ |
| ⚪ LOW | 🔒 | [AIA-08](findings/ai-adapters.md#aia-08) Cover-letter prompt embeds untrusted scraped fields with no delimiter or injection guard | `backend/app/cover_letters/prompts.py:18` | ☐ |
| ⚪ LOW | 🔒 | [AIA-13](findings/ai-adapters.md#aia-13) Scraped job match-summary flows into resume/cover-letter LLM prompts without an injection heuristic | `backend/app/resumes/prompts.py:34` | ☐ |
| ⚪ LOW | 🔒 | [AIA-14](findings/ai-adapters.md#aia-14) Resume LLM prompt ships candidate email to the provider while the cover-letter prompt omits it | `backend/app/resumes/prompts.py:40` | ☐ |
| ⚪ LOW | 🔒 | [AIA-18](findings/ai-adapters.md#aia-18) Summarizer / cover-letter LLM prompts embed scraped fields with no injection guard | `backend/app/summarizers/adapters/openai.py:76` | ☐ |
| ⚪ LOW | 🔒 | [AIA-19](findings/ai-adapters.md#aia-19) LLM adapters POST via raw httpx with no SSRF / outbound-URL guard | `backend/app/summarizers/adapters/openai.py:52` | ☐ |
| ⚪ LOW | 🔒 | [AIA-20](findings/ai-adapters.md#aia-20) Summarizer feeds scraped title/company into the LLM prompt unsanitized (all provider adapters) | `backend/app/summarizers/adapters/openai.py:80` | ☐ |

## WS29 — Inbox classifier/drafter From sanitization & OAuth PKCE
_8 item(s): 3 medium, 5 low._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🔒 | [INB-03](findings/inbox.md#inb-03) Auto-reply recipient is raw inbound From, not checked vs linked employer domain | `backend/app/inbox/reply_message.py:16` | ☐ |
| 🟡 MED | 🔒 | [INB-07](findings/inbox.md#inb-07) Reply-drafter feeds raw inbound From into the LLM with no sanitize or injection guard | `backend/app/services/reply_drafts.py:210` | ☐ |
| 🟡 MED | 🔒 | [INB-09](findings/inbox.md#inb-09) Email classifier sends raw subject/From/To to the LLM with no injection guard | `backend/app/services/email_classification.py:175` | ☐ |
| ⚪ LOW | 🔒 | [INB-11](findings/inbox.md#inb-11) OAuth authorization-code flows omit PKCE across all three providers | `backend/app/inbox/gmail_oauth.py:78` | ☐ |
| ⚪ LOW | 🐞 | [INB-13](findings/inbox.md#inb-13) extract_body_text returns empty for HTML-only multipart mail (no text/plain part) | `backend/app/inbox/parse.py:24` | ☐ |
| ⚪ LOW | 🔒 | [INB-14](findings/inbox.md#inb-14) Client-supplied InboxMessage fields (subject/body_text/raw_headers) have no bounds | `backend/app/inbox/types.py:74` | ☐ |
| ⚪ LOW | 🔁 | [INB-17](findings/inbox.md#inb-17) score_job_match compares In-Reply-To to outbound ids without normalization | `backend/app/services/inbox_linking.py:56` | ☐ |
| ⚪ LOW | 🐞 | [INB-18](findings/inbox.md#inb-18) Message-to-job linking accepts a bare company-name substring as confident match | `backend/app/services/inbox_linking.py:71` | ☐ |

## WS30 — Inbox safe-send, JMAP errors & OAuth-refresh races
_8 item(s): 4 medium, 4 low._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🐞 | [INB-01](findings/inbox.md#inb-01) Fastmail JMAP send/move report success on per-method errors (silent failed auto-send) | `backend/app/inbox/fastmail_jmap.py:246` | ☐ |
| 🟡 MED | 🐞 | [INB-04](findings/inbox.md#inb-04) Sensitive-topic filter misses plain "workers compensation" (auto-reply guard bypass) | `backend/app/inbox/safe_send.py:26` | ☐ |
| 🟡 MED | 🐞 | [INB-06](findings/inbox.md#inb-06) Unlocked concurrent OAuth token refresh rotates Outlook/Yahoo token, breaks mailbox | `backend/app/services/inbox_oauth.py:63` | ☐ |
| 🟡 MED | 🔒 | [INB-08](findings/inbox.md#inb-08) Safe-send topic blocklist scans raw, HTML-encoded, 500-char-truncated inbound body | `backend/app/services/reply_safe_send.py:153` | ☐ |
| ⚪ LOW | ⚡ | [INB-10](findings/inbox.md#inb-10) Gmail poll issues a metadata GET for every listed message (up to ~2000/poll) | `backend/app/inbox/adapters/gmail.py:213` | ☐ |
| ⚪ LOW | ♻️ | [INB-12](findings/inbox.md#inb-12) OAuth-config class list re-enumerated in 4+ sites instead of a shared constant | `backend/app/inbox/mailbox_email.py:16` | ☐ |
| ⚪ LOW | ⚡ | [INB-20](findings/inbox.md#inb-20) Inbox poll resolves each user's mailbox context twice per beat tick (N+1) | `backend/app/services/inbox_orchestration.py:97` | ☐ |
| ⚪ LOW | 🐞 | [INB-23](findings/inbox.md#inb-23) Auto-reply rate caps are check-then-act with no lock; overlap can exceed the cap | `backend/app/services/reply_safe_send.py:80` | ☐ |

## WS31 — Notifier escaping, secret-leak & ntfy topic entropy
_8 item(s): 3 medium, 5 low._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🔒 | [NTF-01](findings/notifiers-worker.md#ntf-01) Unescaped scraped fields in Slack mrkdwn / Discord markdown -> phishing links | `backend/app/notifiers/adapters/slack.py:108` | ☐ |
| 🟡 MED | 🔒 | [NTF-02](findings/notifiers-worker.md#ntf-02) Telegram bot token leaked into persisted DeliveryLog.error and logs via str(HTTPError) | `backend/app/notifiers/adapters/telegram.py:70` | ☐ |
| 🟡 MED | 🔒 | [OPS-16](findings/devops.md#ops-16) ntfy_default_topic defaults to static public topic "headstart-change-me" | `devops/terraform/modules/stack/variables.tf:82` | ☐ |
| ⚪ LOW | 🔒 | [NTF-06](findings/notifiers-worker.md#ntf-06) Default ntfy topic 'headstart-change-me' is a guessable public channel with no entropy requirement, leaking PII | `backend/app/cli/seed.py:61` | ☐ |
| ⚪ LOW | 🔒 | [NTF-08](findings/notifiers-worker.md#ntf-08) Scraped, unvalidated job URLs embedded unescaped into Slack/Discord markup links | `backend/app/notifiers/adapters/slack.py:118` | ☐ |
| ⚪ LOW | 🐞 | [NTF-09](findings/notifiers-worker.md#ntf-09) Webhook notifier user headers can override Content-Type / base headers | `backend/app/notifiers/adapters/webhook.py:116` | ☐ |
| ⚪ LOW | 🔒 | [NTF-10](findings/notifiers-worker.md#ntf-10) User webhook/slack/ntfy URLs (may embed secrets) persisted into DeliveryResult.error via str(HTTPError) | `backend/app/notifiers/adapters/webhook.py:79` | ☐ |
| ⚪ LOW | 🔒 | [XCT-26](findings/cross-cutting.md#xct-26) NTFY_DEFAULT_TOPIC defaults to guessable value and propagates to prod | `devops/terraform/environments/prod/variables.tf:55` | ☐ |

## WS32 — API layer: async offload, param bounds & status codes
_11 item(s): 3 medium, 8 low._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | ⚡ | [API-01](findings/api-schemas.md#api-01) Sync LaTeX subprocess + LLM curation runs inline in generate-resume request | `backend/app/api/v1/jobs.py:78` | ☐ |
| 🟡 MED | ⚡ | [API-02](findings/api-schemas.md#api-02) POST /searches/{id}/run runs the full scrape+summary pipeline synchronously | `backend/app/api/v1/searches.py:54` | ☐ |
| 🟡 MED | 🐞 | [API-04](findings/api-schemas.md#api-04) Out-of-bounds limit/seen_job_id on inbox list routes returns HTTP 500, not 422 | `backend/app/api/v1/inbox.py:227` | ☐ |
| ⚪ LOW | 🔁 | [API-03](findings/api-schemas.md#api-03) GET /feed/rss uses local HTTPException, bypassing central error-shape handlers | `backend/app/api/v1/feed.py:34` | ☐ |
| ⚪ LOW | 🔒 | [API-05](findings/api-schemas.md#api-05) OAuth callback reflects raw provider error query param unencoded into redirect URL | `backend/app/api/v1/inbox.py:86` | ☐ |
| ⚪ LOW | 🔁 | [API-07](findings/api-schemas.md#api-07) Inbox/admin routes use unbounded raw query params instead of Query(ge,le) like siblings | `backend/app/api/v1/inbox.py:198` | ☐ |
| ⚪ LOW | 🔁 | [API-09](findings/api-schemas.md#api-09) List `limit` bounded via schema/min() not Query(ge,le); OpenAPI shows no bounds | `backend/app/api/v1/inbox.py:224` | ☐ |
| ⚪ LOW | 🔁 | [API-10](findings/api-schemas.md#api-10) Live apply returns 200 `queued` for an async-accepted request instead of 202 | `backend/app/api/v1/jobs.py:89` | ☐ |
| ⚪ LOW | 🔁 | [API-11](findings/api-schemas.md#api-11) DELETE /profile/resume(-template) return 200+body, breaking DELETE=204 convention | `backend/app/api/v1/profile.py:69` | ☐ |
| ⚪ LOW | 🔒 | [API-13](findings/api-schemas.md#api-13) ProfileData.answers dict is unbounded unlike the capped skills list | `backend/app/schemas/profile.py:94` | ☐ |
| ⚪ LOW | 🔒 | [API-14](findings/api-schemas.md#api-14) NotificationTarget config is free-form dict with no per-type validation | `backend/app/schemas/target.py:11` | ☐ |

## WS33 — DB performance indexes, N+1 & FK-cascade correctness
_16 item(s): 5 medium, 11 low._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | ⚡ | [DAT-03](findings/data-model.md#dat-03) Missing indexes on seen_job.status/applied_at and application_log.dry_run | `backend/app/models/seen_job.py:36` | ☐ |
| 🟡 MED | ⚡ | [DAT-04](findings/data-model.md#dat-04) recent_failures_for_searches loads all failed deliveries, trims in Python (no SQL LIMIT) | `backend/app/repositories/deliveries.py:361` | ☐ |
| 🟡 MED | ⚡ | [DAT-05](findings/data-model.md#dat-05) Cross-search dedup normalizes user's whole job-URL history in Python per scrape | `backend/app/repositories/jobs.py:60` | ☐ |
| 🟡 MED | 🐞 | [DAT-07](findings/data-model.md#dat-07) Erasure of artifacts/promos relies on DB-only FK cascade, untested (SQLite FK off) | `backend/app/repositories/users.py:113` | ☐ |
| 🟡 MED | 🧪 | [TST-01](findings/test-quality.md#tst-01) Test SQLite engines never set PRAGMA foreign_keys=ON; cascade/FK behavior unenforced | `backend/tests/conftest.py:60` | ☐ |
| ⚪ LOW | 🔁 | [DAT-08](findings/data-model.md#dat-08) Migration omits server_default for NOT NULL text cols that models declare default='' | `backend/alembic/versions/20260630_0031_inbox_reply_send_log.py:33` | ☐ |
| ⚪ LOW | 📝 | [DAT-09](findings/data-model.md#dat-09) ApplicationLog.status comment omits queued/processing states the code stores | `backend/app/models/application_log.py:119` | ☐ |
| ⚪ LOW | ⚡ | [DAT-11](findings/data-model.md#dat-11) seen_job.status has no index despite status-filtered queries in pipeline/ghost/sync paths | `backend/app/models/seen_job.py:842` | ☐ |
| ⚪ LOW | 🔁 | [DAT-12](findings/data-model.md#dat-12) Three user-owned tables cascade only via DB FK, no ORM relationship on User | `backend/app/models/user.py:63` | ☐ |
| ⚪ LOW | ⚡ | [DAT-13](findings/data-model.md#dat-13) delete_for_search re-queries then deletes rows one-by-one instead of bulk DELETE | `backend/app/repositories/digest.py:32` | ☐ |
| ⚪ LOW | ⚡ | [DAT-14](findings/data-model.md#dat-14) Ghost-detection sweep full-scans seen_job (no index on status/applied_at) | `backend/app/repositories/ghost_detection.py:483` | ☐ |
| ⚪ LOW | 🐞 | [DAT-15](findings/data-model.md#dat-15) InboxPollState upsert is non-atomic get-then-insert; concurrent first poll violates unique | `backend/app/repositories/inbox_poll_state.py:20` | ☐ |
| ⚪ LOW | ⚡ | [DAT-16](findings/data-model.md#dat-16) sync_after_scrape materializes every SeenJob row for a search each scrape to diff status | `backend/app/repositories/jobs.py:862` | ☐ |
| ⚪ LOW | ⚡ | [SVC-15](findings/services-pipeline.md#svc-15) DigestService.queue inserts and flushes once per seen_job id in a loop | `backend/app/services/digest.py:40` | ☐ |
| ⚪ LOW | 🧪 | [TST-03](findings/test-quality.md#tst-03) Alembic migration chain never executed by tests (create_all used), hiding PG-only bugs | `backend/tests/conftest.py:61` | ☐ |
| ⚪ LOW | 🧪 | [TST-04](findings/test-quality.md#tst-04) Lock-branch tests monkeypatch _is_sqlite=False on SQLite, asserting nothing about locking | `backend/tests/repositories/test_jobs_deliveries_searches.py:117` | ☐ |

## WS34 — Scraper untrusted-input hardening & URL detection
_6 item(s): 2 medium, 4 low._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🐞 | [SCR-02](findings/scrapers.md#scr-02) Unguarded fromtimestamp on untrusted epoch aborts whole scrape (4 adapters) | `backend/app/scrapers/adapters/google_careers_parse.py:151` | ☐ |
| 🟡 MED | 🔒 | [SCR-04](findings/scrapers.md#scr-04) Scraper HTTP client reads unbounded response bodies — hostile upstream can OOM worker | `backend/app/scrapers/http.py:44` | ☐ |
| ⚪ LOW | 🐞 | [SCR-05](findings/scrapers.md#scr-05) int() of untrusted total crashes on JSON Infinity/NaN in 4 adapters | `backend/app/scrapers/adapters/apple_careers_parse.py:52` | ☐ |
| ⚪ LOW | 🐞 | [SCR-06](findings/scrapers.md#scr-06) Shopify flight-stream resolver recurses with no depth bound (RecursionError DoS) | `backend/app/scrapers/adapters/shopify_careers_parse.py:61` | ☐ |
| ⚪ LOW | 🐞 | [SCR-07](findings/scrapers.md#scr-07) Ashby detector matches any host when path contains 'posting-api/job-board' | `backend/app/scrapers/url_detect.py:110` | ☐ |
| ⚪ LOW | 🔒 | [SCR-08](findings/scrapers.md#scr-08) Microsoft careers host match uses suffix endswith without dot boundary (over-broad) | `backend/app/scrapers/url_detect_microsoft.py:15` | ☐ |

## WS35 — Domain logic: compensation, RSS, alerts & dead code
_8 item(s): 8 low._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| ⚪ LOW | ♻️ | [POR-01](findings/portals.md#por-01) shopify_careers preset ships a dead default_config key `board` the scraper never reads | `backend/app/portals/catalog_helpers.py:186` | ☐ |
| ⚪ LOW | 🐞 | [SVC-09](findings/services-pipeline.md#svc-09) Alerts broadcast to ALL user targets when search has no target | `backend/app/services/application_alerts.py:117` | ☐ |
| ⚪ LOW | ♻️ | [SVC-10](findings/services-pipeline.md#svc-10) derive_pipeline_stage final branch is dead code | `backend/app/services/applications.py:51` | ☐ |
| ⚪ LOW | 🔒 | [SVC-11](findings/services-pipeline.md#svc-11) Adapter payload merged verbatim into stored application_log (no scrub) | `backend/app/services/apply.py:238` | ☐ |
| ⚪ LOW | 🐞 | [SVC-12](findings/services-pipeline.md#svc-12) _annualize treats monthly/weekly/daily comp intervals as already-annual | `backend/app/services/compensation.py:208` | ☐ |
| ⚪ LOW | 🐞 | [SVC-13](findings/services-pipeline.md#svc-13) Compensation parser assumes US number grouping, misreads EU-formatted salaries | `backend/app/services/compensation.py:186` | ☐ |
| ⚪ LOW | 🐞 | [SVC-14](findings/services-pipeline.md#svc-14) Compensation display currency prefix silently falls back to '$' for unknown currencies | `backend/app/services/compensation.py:242` | ☐ |
| ⚪ LOW | 🐞 | [SVC-16](findings/services-pipeline.md#svc-16) RSS builder escapes markup but leaves XML-invalid control chars from scraped fields | `backend/app/services/rss.py:37` | ☐ |

## WS36 — Deploy script & prod Terraform env divergence
_10 item(s): 1 high, 4 medium, 5 low._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟠 HIGH | 🐞 | [OPS-01](findings/devops.md#ops-01) deploy.sh redeploys task defs pinned to a tag never re-pushed by the build | `scripts/deploy.sh:33` | ✅ [PR](https://github.com/davidcristian/HeadStart/pull/9) |
| 🟡 MED | 🔁 | [OPS-05](findings/devops.md#ops-05) Prod block sets RDS AZ/deletion-protection but omits backup + log retention and Redis HA | `devops/terraform/environments/prod/main.tf:23` | ☐ |
| 🟡 MED | 🐞 | [OPS-07](findings/devops.md#ops-07) Prod deploys mutable image_tag "latest" — no immutable pin or rollback | `devops/terraform/environments/prod/variables.tf:11` | ☐ |
| 🟡 MED | 🐞 | [OPS-17](findings/devops.md#ops-17) Deploy rolls all ECS services regardless of DB migration success (fire-and-forget) | `scripts/deploy.sh:26` | ☐ |
| 🟡 MED | 🐞 | [XCT-15](findings/cross-cutting.md#xct-15) HTTP AWS deploy keeps AUTH_COOKIE_SECURE=true, so refresh cookie is dropped | `devops/terraform/modules/stack/main.tf:150` | ☐ |
| ⚪ LOW | 🔁 | [OPS-29](findings/devops.md#ops-29) State backend bucket is unresolved CHANGEME placeholder committed for both envs | `devops/terraform/environments/prod/backend.tf:6` | ☐ |
| ⚪ LOW | 🐞 | [OPS-30](findings/devops.md#ops-30) dev and prod share identical VPC CIDR 10.20.0.0/16 (never overridden) | `devops/terraform/environments/prod/main.tf:1` | ☐ |
| ⚪ LOW | 🔒 | [OPS-31](findings/devops.md#ops-31) Prod provider lacks allowed_account_ids guard against wrong-account apply | `devops/terraform/environments/prod/providers.tf:1` | ☐ |
| ⚪ LOW | 🔒 | [OPS-33](findings/devops.md#ops-33) prod tfvars.example primes inline plaintext secrets in terraform.tfvars | `devops/terraform/environments/prod/terraform.tfvars.example:9` | ☐ |
| ⚪ LOW | 🔒 | [OPS-64](findings/devops.md#ops-64) ECS roll does not pin the just-pushed image digest (build→deploy provenance gap) | `scripts/deploy.sh:33` | ☐ |

## WS37 — CI/pre-commit quality gate & dependency scanning
_12 item(s): 2 medium, 10 low._
_deploy.yml/terraform.yml are dormant — deploy.yml is manual-only (`workflow_dispatch`) and guarded on `vars.AWS_ROLE_ARN`, and terraform.yml's `plan` step is guarded on the same variable — so nothing AWS-touching runs until that variable/secrets are configured. The open WS37 items: the deploy OIDC ref-scoping and terraform-plan-on-PR secrets hardening (OPS-23/OPS-24), dependency scanning, SHA-pinning, and pre-commit/ci parity for LOC/shell/prettier._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🐞 | [OPS-03](findings/devops.md#ops-03) Pre-commit frontend-lint runs eslint with no path: lints 0 files, always passes | `.pre-commit-config.yaml:38` | ☐ |
| 🟡 MED | 🧪 | [OPS-04](findings/devops.md#ops-04) Claimed gates (LOC/shell/prettier) still unenforced: ci.yml omits check_loc/shell-validation/prettier, pre-commit omits them too | `.pre-commit-config.yaml:2` | ☐ |
| ⚪ LOW | 🔒 | [OPS-19](findings/devops.md#ops-19) No dependency vuln scanning (pip-audit / npm audit / Dependabot) in repo | `.github/workflows/ci.yml:1` | ☐ |
| ⚪ LOW | 🔒 | [OPS-20](findings/devops.md#ops-20) All GitHub Actions pinned to floating major-version tags, not commit SHAs | `.github/workflows/ci.yml:20` | ☐ |
| ⚪ LOW | 🐞 | [OPS-21](findings/devops.md#ops-21) CI Slack-failure notify guarded by env var never set at that scope, never fires | `.github/workflows/ci.yml:69` | ☐ |
| ⚪ LOW | 🔁 | [OPS-22](findings/devops.md#ops-22) CI reimplements gate steps inline instead of make check, risking drift | `.github/workflows/ci.yml:29` | ☐ |
| ⚪ LOW | 🔒 | [OPS-23](findings/devops.md#ops-23) Deploy assumes AWS OIDC role with no in-workflow ref scoping or branch-protection note | `.github/workflows/deploy.yml:33` | ☐ |
| ⚪ LOW | 🔒 | [OPS-24](findings/devops.md#ops-24) terraform plan on pull_request injects TF secrets + assumes AWS role on PR code | `.github/workflows/terraform.yml:42` | ☐ |
| ⚪ LOW | 🔒 | [OPS-62](findings/devops.md#ops-62) aws-deploy-env.sh emits terraform/aws outputs into eval'd exports without safe quoting | `scripts/aws-deploy-env.sh:23` | ☐ |
| ⚪ LOW | 🐞 | [OPS-63](findings/devops.md#ops-63) check_loc.sh strips REPO_ROOT via unquoted glob pattern in ${file#...} | `scripts/check_loc.sh:20` | ☐ |
| ⚪ LOW | 🧪 | [OPS-65](findings/devops.md#ops-65) Shell validation is bash -n syntax-only (no shellcheck) | `scripts/validate-shell-scripts.sh:6` | ☐ |
| ⚪ LOW | 🔁 | [OPS-69](findings/devops.md#ops-69) pre-commit formatter pins (ruff 0.5.7 / black 24.8.0) drifted from CI/venv (0.15.20 / 26.5.1) and ran ruff-format on top of black, reformat-looping on clean files | `.pre-commit-config.yaml:18` | ✅ |

## WS38 — Infrastructure hardening (Terraform & Docker)
_18 item(s): 4 medium, 14 low._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🔒 | [OPS-08](findings/devops.md#ops-08) ALB lacks access logs, WAF, deletion protection, and drop_invalid_header_fields | `devops/terraform/modules/alb/main.tf:9` | ☐ |
| 🟡 MED | 🔒 | [OPS-09](findings/devops.md#ops-09) ECR repositories use MUTABLE image tags, allowing tag overwrite | `devops/terraform/modules/ecr/main.tf:7` | ☐ |
| 🟡 MED | 🔒 | [OPS-10](findings/devops.md#ops-10) ElastiCache Redis broker has no in-transit/at-rest encryption and no AUTH token | `devops/terraform/modules/redis/main.tf:9` | ☐ |
| 🟡 MED | 🔒 | [OPS-14](findings/devops.md#ops-14) Tasks security group ingress from ALB opens all TCP ports 0-65535 | `devops/terraform/modules/security/main.tf:61` | ☐ |
| ⚪ LOW | 🔒 | [OPS-27](findings/devops.md#ops-27) Worker image installs playwright system deps as root but retains them at runtime | `backend/Dockerfile:29` | ☐ |
| ⚪ LOW | ⚡ | [OPS-28](findings/devops.md#ops-28) Backend Dockerfile copies app source before pip install, breaking dep caching | `backend/Dockerfile:17` | ☐ |
| ⚪ LOW | 🔒 | [OPS-36](findings/devops.md#ops-36) ALB serves API/frontend over plaintext HTTP when no ACM certificate is configured | `devops/terraform/modules/alb/main.tf:54` | ☐ |
| ⚪ LOW | 🔒 | [OPS-38](findings/devops.md#ops-38) ECS container definitions lack healthCheck, read-only root filesystem, and non-root user | `devops/terraform/modules/ecs/main.tf:40` | ☐ |
| ⚪ LOW | 🔁 | [OPS-40](findings/devops.md#ops-40) Reusable modules declare no required_providers version constraints | `devops/terraform/modules/network/main.tf:1` | ☐ |
| ⚪ LOW | 🔒 | [OPS-41](findings/devops.md#ops-41) VPC has no flow logs enabled | `devops/terraform/modules/network/main.tf:8` | ☐ |
| ⚪ LOW | 🔒 | [OPS-43](findings/devops.md#ops-43) RDS uses AWS-managed KMS key with no IAM auth, Performance Insights, log exports, or CMK rotation | `devops/terraform/modules/rds/main.tf:9` | ☐ |
| ⚪ LOW | 🔒 | [OPS-48](findings/devops.md#ops-48) RDS module: no validation; deletion_protection/final-snapshot default unsafe | `devops/terraform/modules/rds/variables.tf:41` | ☐ |
| ⚪ LOW | 🐞 | [OPS-49](findings/devops.md#ops-49) Redis cluster is single-node with no failover (Celery broker SPOF) | `devops/terraform/modules/redis/main.tf:9` | ☐ |
| ⚪ LOW | 🔒 | [OPS-51](findings/devops.md#ops-51) Secrets Manager secrets use default KMS key and no recovery window set | `devops/terraform/modules/secrets/main.tf:9` | ☐ |
| ⚪ LOW | 🔁 | [OPS-55](findings/devops.md#ops-55) LOG_LEVEL hardcoded to INFO in Terraform with no variable override | `devops/terraform/modules/stack/main.tf:153` | ☐ |
| ⚪ LOW | 🔒 | [OPS-56](findings/devops.md#ops-56) Compose pins local images and ntfy to mutable :latest tags | `docker-compose.yml:111` | ☐ |
| ⚪ LOW | 🐞 | [OPS-57](findings/devops.md#ops-57) api/worker/beat services define no healthcheck; frontend waits on api start not health | `docker-compose.yml:38` | ☐ |
| ⚪ LOW | 🔒 | [OPS-58](findings/devops.md#ops-58) Postgres (and Redis) published to host with weak default creds in compose | `docker-compose.yml:19` | ☐ |

## WS39 — Third-party license & attribution
_2 item(s): 2 low._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| ⚪ LOW | 📝 | [XCT-24](findings/cross-cutting.md#xct-24) No third-party dependency license inventory or NOTICE/attribution bundle | `backend/pyproject.toml:10` | ☐ |
| ⚪ LOW | 📝 | [XCT-25](findings/cross-cutting.md#xct-25) Bundled LGPL-3.0 psycopg relink/source obligation not documented for self-host | `backend/pyproject.toml:16` | ☐ |

## WS40 — Documentation drift
_11 item(s): 11 low._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| ⚪ LOW | 📝 | [AUT-11](findings/auth-security.md#aut-11) config.py inbox_poll comment has botched edit artifact 'new_string classification' | `backend/app/core/config.py:209` | ☐ |
| ⚪ LOW | 📝 | [DOC-06](findings/docs-drift.md#doc-06) api.md endpoint table omits GET/PATCH /summary-preferences | `docs/modules/api.md:87` | ☐ |
| ⚪ LOW | 📝 | [DOC-08](findings/docs-drift.md#doc-08) api.md profile section omits PUT/DELETE /profile/resume-template | `docs/modules/api.md:73` | ☐ |
| ⚪ LOW | 📝 | [DOC-09](findings/docs-drift.md#doc-09) api.md endpoint table omits the entire /inbox/* router (13+ routes) | `docs/modules/api.md:87` | ☐ |
| ⚪ LOW | 📝 | [DOC-11](findings/docs-drift.md#doc-11) api.md omits non-default success statuses (201 create, 204 webhook) | `docs/modules/api.md:84` | ☐ |
| ⚪ LOW | 📝 | [DOC-16](findings/docs-drift.md#doc-16) billing.md says "four public tiers" then lists only Starter, Plus, Pro | `docs/modules/billing.md:7` | ☐ |
| ⚪ LOW | 📝 | [DOC-17](findings/docs-drift.md#doc-17) data-model.md user table omits token_version + 4 AI-preference columns | `docs/modules/data-model.md:40` | ☐ |
| ⚪ LOW | 📝 | [DOC-19](findings/docs-drift.md#doc-19) data-model.md omits real tables (application_artifact, promo_*, data_request_log) | `docs/modules/data-model.md:7` | ☐ |
| ⚪ LOW | 📝 | [DOC-20](findings/docs-drift.md#doc-20) frontend.md says PWA opens on /jobs but start_url is /app/jobs | `docs/modules/frontend.md:166` | ☐ |
| ⚪ LOW | 📝 | [DOC-21](findings/docs-drift.md#doc-21) frontend.md public-routes list omits the shipped /subprocessors route | `docs/modules/frontend.md:25` | ☐ |
| ⚪ LOW | 📝 | [DOC-23](findings/docs-drift.md#doc-23) notifiers.md says ntfy uses URL-path + headers, but adapter POSTs JSON to server root | `docs/modules/notifiers.md:45` | ☐ |

## WS41 — Frontend correctness, a11y, i18n & portals cap
_30 item(s): 1 medium, 29 low._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🐞 | [FRO-07](findings/frontend.md#fro-07) Portals default all-selected exceeds backend portal_ids cap of 30, Search/Subscribe 422s | `frontend/src/pages/portals/usePortalsPage.ts:48` | ☐ |
| ⚪ LOW | 🐞 | [FRO-13](findings/frontend.md#fro-13) 401 refresh has no in-flight dedup: concurrent requests fire N parallel refresh POSTs | `frontend/src/api/client.ts:55` | ☐ |
| ⚪ LOW | 🐞 | [FRO-14](findings/frontend.md#fro-14) parse() throws raw SyntaxError on malformed 2xx body instead of ApiError | `frontend/src/api/client.ts:69` | ☐ |
| ⚪ LOW | 🐞 | [FRO-16](findings/frontend.md#fro-16) refreshSession does not guard resp.json()/network errors, bypassing graceful 401->login | `frontend/src/api/client.ts:61` | ☐ |
| ⚪ LOW | 🔁 | [FRO-17](findings/frontend.md#fro-17) Frontend inbox client drops backend `limit` and reuses Gmail type for Outlook/Yahoo | `frontend/src/api/inbox.ts:17` | ☐ |
| ⚪ LOW | 🔁 | [FRO-18](findings/frontend.md#fro-18) Verify/Onboarding guards omit loading and !user checks, relying implicitly on nesting | `frontend/src/auth/EmailVerificationGuard.tsx:9` | ☐ |
| ⚪ LOW | 🐞 | [FRO-19](findings/frontend.md#fro-19) Apply dialog init-focuses Close and lacks aria-describedby / live status | `frontend/src/components/ApplyJobDialog.tsx:159` | ☐ |
| ⚪ LOW | 🐞 | [FRO-21](findings/frontend.md#fro-21) JsonEditor parse-error message is not an ARIA live region | `frontend/src/components/JsonEditor.tsx:49` | ☐ |
| ⚪ LOW | 🐞 | [FRO-22](findings/frontend.md#fro-22) App shell has no skip-to-content link before the sidebar navigation | `frontend/src/components/Layout.tsx:96` | ☐ |
| ⚪ LOW | 🐞 | [FRO-24](findings/frontend.md#fro-24) Resume/template uploads have no client-side size/type gate despite stated limits | `frontend/src/components/profile/ProfileDetailsForm.tsx:146` | ☐ |
| ⚪ LOW | 🔁 | [FRO-25](findings/frontend.md#fro-25) SkillsLanguagesForm redefines updateRow instead of importing profileFormUtils | `frontend/src/components/profile/SkillsLanguagesForm.tsx:19` | ☐ |
| ⚪ LOW | 🐞 | [FRO-26](findings/frontend.md#fro-26) Checkbox rows nest a <label> inside the Field <label> (invalid HTML, ambiguous a11y) | `frontend/src/components/profile/WorkExperienceSection.tsx:120` | ☐ |
| ⚪ LOW | 🐞 | [FRO-27](findings/frontend.md#fro-27) parseOptionalInt accepts negative/decimal years and months (min/max not enforced) | `frontend/src/components/profile/profileFormUtils.ts:3` | ☐ |
| ⚪ LOW | 🔁 | [FRO-28](findings/frontend.md#fro-28) SMTP password field lacks the 'write-only' hint its IMAP-password sibling carries | `frontend/src/components/settings/SettingsInboxImapForm.tsx:54` | ☐ |
| ⚪ LOW | 🐞 | [FRO-29](findings/frontend.md#fro-29) Shared Banner has no ARIA live-region role; async errors/success never announced | `frontend/src/components/ui.tsx:59` | ☐ |
| ⚪ LOW | 🐞 | [FRO-30](findings/frontend.md#fro-30) useUpdateJob invalidates only ["jobs"], leaving the applications pipeline stale | `frontend/src/hooks/jobMutations.ts:13` | ☐ |
| ⚪ LOW | 🐞 | [FRO-31](findings/frontend.md#fro-31) useApplyToJob invalidates ["jobs"] only on sync submitted, not the async queued path | `frontend/src/hooks/jobMutations.ts:46` | ☐ |
| ⚪ LOW | 🐞 | [FRO-32](findings/frontend.md#fro-32) useFocusTrap re-runs on onClose identity change, stealing focus and breaking restore | `frontend/src/hooks/useFocusTrap.ts:68` | ☐ |
| ⚪ LOW | 🐞 | [FRO-33](findings/frontend.md#fro-33) CSS uses undefined vars --surface/--accent/--bg-muted with no fallback | `frontend/src/index.css:1523` | ☐ |
| ⚪ LOW | 🔁 | [FRO-34](findings/frontend.md#fro-34) Date/time rendered in the browser's implicit locale and timezone with no fixed formatting | `frontend/src/lib/format.ts:16` | ☐ |
| ⚪ LOW | 🔁 | [FRO-35](findings/frontend.md#fro-35) Billing and pricing are USD-only while the product legally targets the German market | `frontend/src/lib/pricing.ts:176` | ☐ |
| ⚪ LOW | 🔁 | [FRO-36](findings/frontend.md#fro-36) Admin scrape-errors and Users cards render blank while loading | `frontend/src/pages/AdminPage.tsx:124` | ☐ |
| ⚪ LOW | 🔁 | [FRO-37](findings/frontend.md#fro-37) German legal pages display effective dates in US English long format | `frontend/src/pages/ImpressumPage.tsx:6` | ☐ |
| ⚪ LOW | 🐞 | [FRO-38](findings/frontend.md#fro-38) Jobs filter <select>s wrapped in <Field label=""> have an empty accessible name | `frontend/src/pages/JobsPage.tsx:148` | ☐ |
| ⚪ LOW | 🐞 | [FRO-39](findings/frontend.md#fro-39) Onboarding progress steps convey current step only via CSS class, not aria-current | `frontend/src/pages/OnboardingPage.tsx:28` | ☐ |
| ⚪ LOW | 🐞 | [FRO-41](findings/frontend.md#fro-41) Category tablists have role=tab but no linked tabpanel or roving tabindex | `frontend/src/pages/sources/PortalCatalog.tsx:71` | ☐ |
| ⚪ LOW | ♻️ | [FRO-42](findings/frontend.md#fro-42) tsconfig omits noUncheckedIndexedAccess for a hand-typed API client | `frontend/tsconfig.json:14` | ☐ |
| ⚪ LOW | 🔁 | [NTF-12](findings/notifiers-worker.md#ntf-12) User-facing notification and email copy is hardcoded English with no localization hook | `backend/app/notifiers/digest_format.py:17` | ☐ |
| ⚪ LOW | 🧪 | [TST-07](findings/test-quality.md#tst-07) Test asserts 'submitted' apply-result behavior the API never produces (coverage-theater) | `frontend/src/hooks/jobMutations.test.tsx:79` | ☐ |
| ⚪ LOW | 🐞 | [XCT-27](findings/cross-cutting.md#xct-27) useApplyToJob 'submitted' jobs-cache invalidation branch is unreachable (dead code) | `frontend/src/hooks/jobMutations.ts:46` | ☐ |

## WS42 — Delta follow-ups (2026-07-03)
_7 item(s): 1 medium, 6 low. Recorded by a scoped re-audit of the post-baseline fix wave; full context in [findings/](findings/)._

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🐞 | [APL-28](findings/appliers.md#apl-28) Apple apply_error_message only rejects strict success:false; bare-errors 200 bodies still report submitted | `backend/app/appliers/adapters/apple_careers_common.py:158` | ☐ |
| ⚪ LOW | 🔒 | [APL-29](findings/appliers.md#apl-29) Indeed Cookie header built by manual join of unvalidated credential values (self header-injection) | `backend/app/appliers/adapters/indeed.py:175` | ☐ |
| ⚪ LOW | 🔁 | [OPS-67](findings/devops.md#ops-67) loc-cap exempts */tests/* but frontend src/test/ stays capped, disagreeing with the coverage-gate exclusion | `scripts/check_loc.sh:20` | ☐ |
| ⚪ LOW | 🔒 | [OPS-68](findings/devops.md#ops-68) loc-cap exemption keys on the tests/ path segment, not on being a test | `scripts/check_loc.sh:20` | ☐ |
| ⚪ LOW | 📝 | [DOC-24](findings/docs-drift.md#doc-24) AGENTS.md §6 understates the frontend coverage exclusions (self-declared DoD violation) | `AGENTS.md` | ☐ |
| ⚪ LOW | 📝 | [DOC-25](findings/docs-drift.md#doc-25) README lists ntfy in the make up service set, but make up never starts it | `README.md:93` | ☐ |
| ⚪ LOW | 🧪 | [TST-08](findings/test-quality.md#tst-08) src/test/** gate exclusion + deletion of mockApiSamples.test.ts left the mock builders unasserted | `frontend/src/test/mockApiSamples.ts` | ☐ |
