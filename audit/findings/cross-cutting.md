# Cross-cutting — findings spanning >=3 modules

This area collects findings that are not confined to a single module but recur across layers or subsystems: worker-pipeline concurrency and before-commit correctness, plan/feature schema drift between backend and frontend, supply-chain and dependency-pinning gaps, third-party license attribution, deployment/config drift, HTTP security headers, and systemic frontend security. The headline: a cluster of confirmed **before-commit / unlocked-queue race conditions** in the Celery worker pipeline can double-send recruiter emails and even double-submit live job applications, and a persistent **`portal_search` schema-drift** bug silently gates a paid feature off for every entitled user. A long tail of medium/low findings covers licensing, dependency pinning, SSRF/DNS-rebinding, and deployment config coupling.

**Summary:** 0 critical · 3 high · 15 medium · 9 low (27 findings total).

Note on merges: the `portal_search` schema-drift defect surfaced from three angles (backend schema XCT-06/XCT-07, frontend type XCT-18) — these are the same root cause and are rolled into a single consolidated finding (**XCT-06**). The two GDPR-export-completeness findings (XCT-09, XCT-10) are the same defect from two overlapping evidence sets and are merged into **XCT-09**. That leaves 24 distinct rendered findings below (all 27 ids preserved and cross-referenced).

---

<a id="xct-01"></a>
### XCT-01 — Pending auto-reply queue has no lease; overlapping ticks double-send recruiter emails
🟠 **HIGH** · 🐞 bug · Status: ✅ done · Confidence: high (5/5 verifiers) · Effort: M · WS14

**Locations:** `backend/app/repositories/inbox_pending_replies.py:24` (`InboxPendingReplyRepository.list_due`); plus `backend/app/services/pending_replies.py:133`, `backend/app/services/pending_replies.py:205`, `backend/app/worker/tasks.py:177`.

**Evidence.** `list_due` selects `status == 'pending'` rows with no `FOR UPDATE SKIP LOCKED` and no in-flight marking, so due rows are never leased. `_send_one` sends SMTP first and only then sets `status='sent'` and flushes, and `session_scope` commits only after the whole batch. Two overlapping `process_pending_replies` ticks therefore select the same due row. This violates the WS2 `claim_due` convention already used elsewhere (`searches.py:69`).

**Failure scenario.** An SMTP send batch exceeds the 60s `inbox_reply_send_interval` (or an `acks_late` redelivery occurs), so the next beat tick re-selects still-`pending` rows and re-sends — the recruiter receives duplicate autonomous replies.

**Suggested fix.** Mirror WS2 `claim_due`: row-lock/claim due rows (`FOR UPDATE SKIP LOCKED` on Postgres) and flip status to an in-flight state before send, re-checking under the lock.

**Verification.** Confirmed 5/5 adversarial verifiers. `list_due` lacks `FOR UPDATE SKIP LOCKED`/in-flight flip; `session_scope` commits only after the whole batch, and `_send_one` sends SMTP before flushing status, so overlapping ticks / `acks_late` redelivery double-send recruiter emails.

<a id="xct-02"></a>
### XCT-02 — enqueue_apply read-then-write with no unique constraint double-submits live applications
🟠 **HIGH** · 🐞 bug · Status: ✅ done · Confidence: high (5/5 verifiers) · Effort: M · WS14

**Locations:** `backend/app/services/apply.py:49` (`ApplyService.enqueue_apply`); plus `backend/app/services/apply.py:72`, `backend/app/repositories/application_logs.py:38`, `backend/app/models/application_log.py:16`, `backend/app/api/v1/jobs.py:109`.

**Evidence.** `get_pending_for_job` (SELECT queued/processing) is followed by `application_logs.add` (INSERT) with no lock and no partial-unique constraint. Two concurrent `POST /jobs/{id}/apply` both pass the guard, insert two `queued` logs, and dispatch two `apply_to_job_task` → two live submissions. The same read-then-write pattern exists in `enqueue_auto_apply_from_pipeline`.

**Failure scenario.** User double-clicks Apply or the client retries: two `apply_to_job` tasks run and the employer receives two identical live applications for one job.

**Suggested fix.** Add a DB partial-unique on `(seen_job_id)` where `status in (queued, processing)` with `IntegrityError` handling, or `SELECT ... FOR UPDATE` the `seen_job` before the pending check.

**Verification.** Confirmed 5/5 adversarial verifiers. `enqueue_apply` reads unlocked `get_pending_for_job` then inserts a queued log; `application_log` has no unique constraint on `seen_job_id` and `jobs.py:109` has no idempotency guard, so two concurrent `POST /apply` dispatch two live employer submissions.

**Resolution.** Fixed in `334164a` (migration `0036_application_log_inflight`): partial unique index `uq_application_log_inflight_job` plus `try_add_pending` SAVEPOINT/`IntegrityError` handling. Tracker/docs aligned in the XCT-02 backlog-drain PR (same root defect as **SVC-01**).

<a id="xct-03"></a>
### XCT-03 — process_pending_replies has no row lock; redelivery double-sends recruiter SMTP reply
🟠 **HIGH** · 🐞 bug · Status: ✅ done · Confidence: high (5/5 verifiers) · Effort: M · WS14

**Locations:** `backend/app/services/pending_replies.py:133` (`PendingReplyService.process_due`); plus `backend/app/repositories/inbox_pending_replies.py:24`, `backend/app/worker/celery_app.py:25`, `backend/app/worker/tasks.py:177`.

**Evidence.** `list_due()` selects `status == 'pending'` with NO `FOR UPDATE`/`SKIP LOCKED` (unlike `digest.flush_due`). `_send_one` flips status to `'sent'` only *after* `inbox.send_message` succeeds. With `task_acks_late=True` and `max_retries=0`, a redelivered task overlapping the next tick both read the row and both send. This is the same unlocked-queue defect as XCT-01, viewed from the service-layer send path.

**Failure scenario.** Worker dies after the SMTP send but before commit; the redelivered task overlaps the next tick → the recruiter receives the same auto-reply twice.

**Suggested fix.** Lock each due row with `SELECT ... FOR UPDATE SKIP LOCKED` and re-check `status == 'pending'` under the lock before sending (mirror `digest.flush_due`).

**Verification.** Confirmed 5/5 adversarial verifiers. `list_due` selects pending with no `FOR UPDATE`/`SKIP LOCKED`, unlike `digest.flush_due`; with `task_acks_late` a crash between SMTP send and commit leaves the row pending so a redelivered/overlapping task re-sends the recruiter auto-reply.

<a id="xct-05"></a>
### XCT-05 — Single stored AI key sent to whichever provider a purpose resolves to
🟡 **MEDIUM** · 🔒 security · Status: ✅ done · Confidence: high (3/5 verifiers) · Effort: M · WS28

**Locations:** `backend/app/ai/runtime_settings.py:111` (`resolve_ai_settings`); plus `backend/app/services/summary_preferences.py:139`, `backend/app/models/user.py:57`, `backend/app/ai/runtime_settings.py:113`.

**Evidence.** A user has ONE `summary_api_key_ciphertext` but per-purpose provider overrides (`ai_purpose_providers`). `resolve_ai_settings` decrypts that single key and assigns `api_key_overrides[provider]` for whichever provider the purpose resolves to, regardless of which provider the key actually belongs to.

**Failure scenario.** A user sets global `provider=openai` (key = OpenAI secret) and an `email_draft` override of `gemini`. Drafting then sends the OpenAI secret to Google as `x-goog-api-key`, disclosing the key to a different vendor.

**Fix ([PR](https://github.com/davidcristian/HeadStart/pull/47)).** `resolve_ai_settings` attaches the decrypted user key only when the resolved purpose provider equals `user.summary_provider` (the provider the key was entered for). Crossed purpose overrides fall back to the deployment/env key for that vendor.

**Verification.** Confirmed 3/3 adversarial verifiers. Single key assigned to `api_key_overrides[resolved_provider]` (`runtime_settings.py:111`) regardless of origin; `gemini.py:40` + `llm_common.py:61` send it as `x-goog-api-key`. A crossed purpose override leaks the user's key to another vendor, though the misconfiguration is self-inflicted.

<a id="xct-06"></a>
### XCT-06 — PlanFeaturesRead omits portal_search; /meta strips it and Pro portal search is gated off for all
🟡 **MEDIUM** · 🐞 bug · Status: ✅ done · Confidence: high (5/5 verifiers) · Effort: XS · WS17

**Locations:** `backend/app/schemas/plan.py:22` (`PlanFeaturesRead`); plus `backend/app/services/plan_limits.py:83`, `backend/app/api/v1/health.py:32`, `frontend/src/pages/portals/usePortalsPage.ts:11`, `frontend/src/types/meta.ts:20`.

**Merged finding.** This consolidates three reports of the same root defect: **XCT-06** and **XCT-07** (backend `PlanFeaturesRead` missing the field, at `plan.py:26` and `plan.py:22`) and **XCT-18** (frontend `PlanFeatures.portal_search` at `meta.ts:20` never receiving a value). All three describe one broken end-to-end contract.

**Evidence.** `plan_limits.snapshot()` builds the features dict *with* `portal_search` (`plan_limits.py:83`), and `health.py:32` does `AccountPlanRead.model_validate(snapshot)`. But `PlanFeaturesRead` declares only four fields (`digest_mode`, `ai_summaries`, `site_credentials`, `rss_feed`) — no `portal_search` — and does not set `extra='allow'`, so Pydantic v2's default `extra='ignore'` silently drops the key. The frontend type declares `portal_search: boolean`, and `usePortalsPage.ts:11` reads `features.portal_search ?? false`, so the flag is always `false`.

**Failure scenario.** A Pro/Plus user (`portal_search=True` in `core/plans.py`) opens the Portals page; `/meta` never carries `portal_search`, so `portalSearchAllowed` falls back to `false` and the paid cross-portal search stays disabled/hidden for every entitled user. (Note: the backend `require_portal_search` gate still enforces access server-side, so this is UI-only — but it hides a paid feature entirely.)

**Fix.** Add `portal_search: bool` to `PlanFeaturesRead` so `AccountPlanRead.model_validate(snapshot)` keeps the flag for `/meta` and the Portals UI. Same root defect as API-12. See [PR](https://github.com/davidcristian/HeadStart/pull/23).

**Verification.** Confirmed across all reports (5/5, 3/3, and 5/5 verifiers respectively). `PlanFeaturesRead` omits `portal_search` though `snapshot()` emits it; `model_validate` with Pydantic `extra='ignore'` drops it, so `/meta` never returns it and `usePortalsPage.ts:11` defaults to `false`, gating the Pro-only Portals feature off for everyone.

<a id="xct-08"></a>
### XCT-08 — Admin deactivate then reactivate resurrects pre-deactivation tokens (no version bump)
🟡 **MEDIUM** · 🔒 security · Status: ✅ done · Confidence: high (5/5 verifiers) · Effort: S · WS17

**Locations:** `backend/app/services/admin.py` (`AdminService.update_user`); plus `backend/app/repositories/users.py` (`bump_token_version`), `backend/app/api/deps.py`.

**Evidence.** `update_flags` flipped `is_active` but never called `bump_token_version`. `get_current_user`/refresh only reject a stale `ver`; `is_active` alone gates access. Tokens carry a `ver` that was unchanged across a deactivate + reactivate cycle.

**Failure scenario.** An admin deactivates a compromised/abusive account to lock it out, then later reactivates it; any access/refresh JWT minted before deactivation that is still within its lifetime works again — the lock-out was not durable.

**Fix.** `AdminService.update_user` bumps `token_version` when `is_active` transitions to `False`, so pre-deactivation JWTs stay invalid after reactivation. Idempotent when the account is already inactive; plan-only updates do not bump. See [PR](https://github.com/davidcristian/HeadStart/pull/24).

**Verification.** Confirmed 5/5 adversarial verifiers. `update_flags` never bumped `token_version`; `deps.py` gates on `is_active` and `ver == token_version`, so deactivate-then-reactivate left `ver` unchanged and pre-deactivation JWTs within their window validated again. The exploit requires reactivation inside the token lifetime, so medium.

<a id="xct-09"></a>
### XCT-09 — Data export omits most user-owned tables (applications, artifacts, inbox, delivery, resume bytes, promos)
🟡 **MEDIUM** · 🐞 bug · Status: ✅ done · Confidence: high (5/5 verifiers) · Effort: L · WS18

**Merged finding.** Consolidates **XCT-09** and **XCT-10**, which flag the same incomplete-GDPR-export defect (one framed as bug/portability, one as security/PII). Both point at `export_user_data` and the same set of omitted `user_id`-owned tables. Same root cause as **AUT-32**.

**Evidence.** `UserDataExport` previously bundled only `account`/`sources`/`searches`/`targets`/`credentials`/`profile`/`jobs`. `profile` is `ProfileRead`, whose `resume_file` is `ResumeFileMeta` (filename/size, NOT the bytes). Excluded entirely: `application_log`, `application_artifact`, `delivery_log`, `inbox_classification`/`reply_draft`/`pending_reply`/`reply_send_log`/`mailbox_credential`, and `promo_redemption` — all `user_id`-scoped PII tables.

**Failure scenario.** A user exercising GDPR Art.15/20 portability receives an export missing their uploaded resume content, tailored-resume PDFs, application history, notification/delivery logs, stored recruiter-email drafts, and promo redemptions — materially incomplete.

**Fix ([PR](https://github.com/davidcristian/HeadStart/pull/29)).** `UserDataExport` `format_version` is now `2` and includes applications, artifacts (decrypted `data_b64`), deliveries, mailbox metadata (secrets redacted), inbox classifications/drafts/pending replies/send logs, promo redemptions, plus `resume_file` / `resume_template` bytes. Builder lives in `auth_account_export.py`. Also closes AUT-32 and restores the corrupted auth.md export sentence (DOC-13/DOC-15).

<a id="xct-11"></a>
### XCT-11 — detect_ghosted_applications unlocked, sets ghosted_at after send; overlap double-emails
🟡 **MEDIUM** · 🐞 bug · Status: ✅ done · Confidence: medium (3/5 verifiers) · Effort: M · WS14

**Locations:** `backend/app/services/ghost_detection.py` (`GhostDetectionService.claim_due_ids` / `process_claimed`); plus `backend/app/repositories/ghost_detection.py`, `backend/app/worker/tasks.py`.

**Evidence.** `list_stale_applications` selected rows with `ghosted_at IS NULL`; `_process_job` called `inbox.send_message()` and only then set `job.ghosted_at`. There was no `FOR UPDATE` and no re-check under a lock. A redelivered (`acks_late`) detect task overlapping the next tick both saw `ghosted_at` NULL and both sent. Same family of defect as XCT-01/03/12.

**Failure scenario.** Two overlapping ghost-detection passes for the same stale application both send the self-summary before either commits `ghosted_at` → the user gets the ghost summary twice.

**Fix.** Claim candidates with `SELECT ... FOR UPDATE SKIP LOCKED`, stamp `ghosted_at`, and commit the lease before SMTP (`claim_due_ids` then `process_claimed` across two `session_scope` transactions). Failed sends / unexpected raises release `ghosted_at` so the next tick can retry. See [PR](https://github.com/davidcristian/HeadStart/pull/16).

**Verification.** Confirmed 3/3 adversarial verifiers. `list_stale_applications` filtered `ghosted_at IS NULL` with no `FOR UPDATE`/`SKIP LOCKED` or claim step; send happened before `ghosted_at` was set+flushed (not committed), so an overlapping pass in a separate transaction still saw NULL and re-sent. Recoverable duplicate email requiring concurrency preconditions.

<a id="xct-12"></a>
### XCT-12 — run_search notifies before commit; acks-late redelivery re-notifies same jobs
🟡 **MEDIUM** · 🐞 bug · Status: ✅ done · Confidence: high (3/5 verifiers) · Effort: L · WS14

**Locations:** `backend/app/services/pipeline.py` (`PipelineService.run`); plus `backend/app/services/pipeline_delivery.py`, `backend/app/worker/tasks.py`, `backend/app/core/db.py`.

**Evidence.** `_notify` called `notifier.send()` (a side effect) inside `run()`; dedup relied on `SeenJob` rows persisted in the same `session_scope` that committed only after the task returned. With `acks_late` + `max_retries=0`, a crash between send and commit rolled back the `SeenJob` inserts, so on redelivery `_dedupe` found nothing and `_notify` fired again. There was no unique constraint on `DeliveryLog` to guard against this.

**Failure scenario.** Worker killed (OOM/deploy) after emails/webhooks are sent but before commit; the redelivered `run_search` re-scrapes and re-notifies the same new jobs → duplicate job alerts.

**Fix.** Persist new `seen_job` rows and `session.commit()` before immediate `notifier.send`, so a mid-send crash leaves durable dedup state for redelivery. Digest mode still queues in the open transaction (no external side effect yet). Delivery helpers live in `pipeline_delivery.py`. See [PR](https://github.com/davidcristian/HeadStart/pull/17).

**Verification.** Confirmed 3/3 adversarial verifiers. `run()` ran inside a `session_scope` that committed only at task end; `_notify` sent before commit; `acks_late` redelivered on worker death, and the `SeenJob` rollback let `_dedupe` miss and re-notify.

<a id="xct-13"></a>
### XCT-13 — Every prefork worker child binds the same metrics port -> EADDRINUSE crash loop
🟡 **MEDIUM** · 🐞 bug · Status: ✅ done · Confidence: high (3/5 verifiers) · Effort: S · WS15

**Locations:** `backend/app/worker/celery_app.py:33` (`_start_worker_metrics_server`); plus `backend/app/core/metrics.py:96`, `backend/docker-entrypoint.sh:12`.

**Evidence.** `@worker_process_init.connect` runs `start_metrics_server(settings.metrics_port)` in EVERY child; `metrics_enabled` defaults `True` and the port is fixed at 9090. The entrypoint runs `celery worker` with no `--concurrency`, so concurrency equals CPU count. `start_http_server` binds a live listener, and the second child gets `EADDRINUSE`.

**Failure scenario.** Deploy the worker on any host with more than one vCPU. The first child binds `:9090`; every other child crashes on init with "Address already in use", Celery respawns them → crash loop and degraded concurrency.

**Suggested fix.** Bind the metrics server once per OS process (`worker_init`, not per-child), or use a per-child port / skip it in prefork children.

**Verification.** Confirmed 3/3 adversarial verifiers. `worker_process_init` binds fixed port 9090 (`metrics_enabled` default `True`) in every prefork child; the entrypoint runs `celery worker` with no `--concurrency`, so on any >1 vCPU host the children after the first hit `EADDRINUSE` in `start_http_server`.

<a id="xct-14"></a>
### XCT-14 — Backend deps all floating >= floors, no lockfile: non-reproducible builds
🟡 **MEDIUM** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/20)) · Confidence: high (3/5 verifiers) · Effort: M · WS15

**Update (2026-07-10).** Fixed in [PR](https://github.com/davidcristian/HeadStart/pull/20): committed hashed pip-tools lockfiles
(`backend/requirements.txt`, `requirements-dev.txt`, `requirements-playwright.txt`);
Docker, CI, and `just setup` install with `--require-hashes` then `--no-deps` for
the local package. Regenerate via `just lock-backend` ([ADR-0012](../../docs/adr/0012-backend-dependency-lockfiles.md)).

**Locations:** `backend/pyproject.toml:10` (`[project].dependencies`).

**Evidence.** All 19 runtime deps use open lower bounds (`fastapi>=0.111`, `sqlalchemy>=2.0.30`, `cryptography>=42.0`, `celery[redis]>=5.4`) with no upper cap and NO committed lockfile/constraints (only the frontend has `package-lock.json`). `pip install -e backend` resolves whatever PyPI serves that day.

**Failure scenario.** Two builds days apart (CI vs prod) pull different transitive versions; a breaking major, or a yanked/compromised release, lands silently in the ECS image with no review.

**Suggested fix.** Add a committed lockfile (pip-tools/uv, with hashes) and install from it in Docker + CI; keep the `pyproject` floors for humans but resolve from the lock for builds.

**Verification.** Confirmed 3/3 adversarial verifiers. All 19 runtime deps use open `>=` floors with no upper cap and no committed backend lockfile/constraints (only frontend has `package-lock.json`); `pip install -e` resolves unpinned.

<a id="xct-15"></a>
### XCT-15 — HTTP AWS deploy keeps AUTH_COOKIE_SECURE=true, so refresh cookie is dropped
🟡 **MEDIUM** · 🐞 bug · Status: ☐ open · Confidence: high (5/5 verifiers) · Effort: S · WS36

**Locations:** `devops/terraform/modules/stack/main.tf:150` (`ecs_environment`); plus `backend/app/core/config.py:54`, `backend/app/api/v1/auth.py:37`, `docs/deploying-to-aws.md:74`.

**Evidence.** Without `domain_name`, `app_base_url = 'http://<alb-dns>'` (`stack/main.tf:24-28`) and `FRONTEND_BASE_URL` is set to it (l.161), but `ecs_environment` never sets `AUTH_COOKIE_SECURE`; the config default is `True` (`config.py:54`). `set_cookie(secure=True)` over plain HTTP means the browser drops the refresh cookie.

**Failure scenario.** An operator follows the documented default (no custom domain, HTTP on the ALB). Users log in, but the httpOnly refresh cookie is never stored; every 30-minute access-token expiry logs them out with no refresh.

**Suggested fix.** Derive `AUTH_COOKIE_SECURE` from `https_enabled` in `ecs_environment` (false when HTTP), or expose it as a variable; document the coupling in `deploying-to-aws.md`.

**Verification.** Confirmed 5/5 adversarial verifiers. `ecs_environment` never sets `AUTH_COOKIE_SECURE`; the config default is `True` and the ALB forwards plain HTTP when no cert is present, so the secure cookie is dropped and refresh auth silently fails on the documented no-domain default. Recoverable functional breakage, so medium.

<a id="xct-16"></a>
### XCT-16 — SPA served with no CSP, X-Frame-Options, HSTS, X-Content-Type-Options or Referrer-Policy
🟡 **MEDIUM** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/35)) · Confidence: high (3/5 verifiers) · Effort: S · WS20

**Update (2026-07-10).** Fixed: `frontend/nginx.conf` `location /` emits CSP (`frame-ancestors 'none'`), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, HSTS, and `Permissions-Policy` with `always`; asset/SW locations restate `nosniff` (nginx `add_header` inheritance). Also closes [FRO-11](frontend.md#fro-11) — [PR](https://github.com/davidcristian/HeadStart/pull/35).

**Locations:** `frontend/nginx.conf:1` (`server`); plus `backend/app/main.py:28`, `devops/terraform/modules/alb/variables.tf:9`, `frontend/Dockerfile:16`.

**Evidence.** `nginx.conf` sets only `Cache-Control`; grepping `content-security-policy|x-frame-options|strict-transport-security|x-content-type-options|referrer-policy|permissions-policy` across all `*.conf`/`*.tf`/`*.yml` returns nothing. The frontend is this nginx image behind an ALB (no CloudFront), so no upstream injects them either.

**Failure scenario.** The authenticated SPA (which handles PII/credentials) can be framed (clickjacking), has no CSP to blunt injected-script/XSS token exfiltration, no HSTS to prevent TLS downgrade, and unrestricted MIME-sniffing.

**Suggested fix.** Add `add_header` directives for `Content-Security-Policy`, `X-Frame-Options`/`frame-ancestors`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, and `Strict-Transport-Security` (with `always`).

**Verification.** Confirmed 3/3 adversarial verifiers. `nginx.conf` sets only `Cache-Control`; grep across conf/tf/yml/py finds no CSP/X-Frame/HSTS/nosniff/Referrer-Policy, no CloudFront, and the backend has only CORS middleware, so the authenticated PII SPA ships with no security headers.

<a id="xct-17"></a>
### XCT-17 — Scraped, unvalidated job URLs rendered into href enable javascript:-scheme XSS
🟡 **MEDIUM** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/22)) · Confidence: high (5/5 verifiers) · Effort: M · WS16

**Update (2026-07-10).** Fixed: shared `safeHref()` allows only `http`/`https`; the five scraped-URL anchors render plain text when the scheme is unsafe — [PR](https://github.com/davidcristian/HeadStart/pull/22).

**Locations:** `frontend/src/components/JobList.tsx:134` (`JobTitle`); plus `frontend/src/components/ApplicationPipelineList.tsx:164`, `frontend/src/components/SearchHealth.tsx:55`, `frontend/src/components/profile/ApplicationHistoryTable.tsx:44`, `frontend/src/pages/portals/PortalsResultsCard.tsx:38`, `backend/app/scrapers/adapters/generic_html.py:78`, `backend/app/scrapers/types.py:19`, `backend/app/schemas/job.py:22`.

**Evidence.** `<a href={job.url} target="_blank">` renders a scraped URL with no scheme check. `JobPosting.url: str = ""` / `JobRead.url: str` never validate the scheme, and `generic_html._href` does `urljoin(base_url, href)`, which returns `javascript:...` verbatim. React does not strip `javascript:` hrefs. This is a systemic pattern across at least five components:

- `frontend/src/components/JobList.tsx:134`
- `frontend/src/components/ApplicationPipelineList.tsx:164`
- `frontend/src/components/SearchHealth.tsx:55`
- `frontend/src/components/profile/ApplicationHistoryTable.tsx:44`
- `frontend/src/pages/portals/PortalsResultsCard.tsx:38`

**Failure scenario.** An attacker-controlled job board (or a user's own `generic_html` source pointed at a hostile page) yields a posting whose href is `javascript:fetch('/x?c='+document.cookie)`. The victim clicks the job title / View link → the script runs in the app origin.

**Suggested fix.** Validate the URL scheme to http/https at scraper normalization (reject/blank others) and add a shared `safeHref()` guard used by every `<a href={untrusted}>`; drop non-http(s) links.

**Verification.** Confirmed 5/5 adversarial verifiers. `generic_html._href` does a bare `urljoin` (no scheme check), `JobPosting`/`JobRead.url` are plain `str` with no validator, and multiple components render `<a href={untrusted}>` directly; no `safeHref` util exists — React renders `javascript:` hrefs, so scraped content yields XSS in the app origin.

<a id="xct-19"></a>
### XCT-19 — LinkedIn/Indeed credentialed scrape + auto-apply is under-disclosed ToS/CFAA risk
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: medium (2/3 verifiers) · Effort: M · WS25

**Locations:** `backend/app/appliers/adapters/linkedin_common.py:9` (`LinkedIn apply/scrape`); plus `backend/app/scrapers/adapters/linkedin.py:129`, `backend/app/scrapers/adapters/indeed.py:12`, `backend/app/appliers/adapters/linkedin_easy_apply_form.py:1`, `frontend/src/pages/TermsOfUsePage.tsx:53`.

**Evidence.** `linkedin.py:129` injects the user's session cookies via Site credentials to defeat authwalls; `linkedin_easy_apply_form.py` drives authenticated Voyager Easy-Apply; `indeed.py:12` uses saved cookies to "pass the challenge" (Cloudflare). LinkedIn/Indeed ToS prohibit automated access/scraping.

**Failure scenario.** The SaaS automates access to LinkedIn/Indeed with members' own credentials at scale; the operator/users risk account bans, cease-and-desist, or CFAA liability. The Terms shift blame to users, but the product enables the violation.

**Suggested fix.** Add per-adapter legal-risk disclaimers + opt-in consent gating for LinkedIn/Indeed, and document the ToS exposure in `appliers.md`/`scrapers.md`.

**Verification.** Confirmed 2/3 adversarial verifiers (1 refuted). Code confirms credentialed LinkedIn/Indeed scraping + auth-wall bypass, but ToS disclosure already exists (`TermsOfUsePage.tsx:39,54`) and this is a legal/documentation hardening ask, not a code defect; the original medium rating was downgraded to low.

<a id="xct-20"></a>
### XCT-20 — Worker /metrics HTTP server ignores metrics_token — unauthenticated even when set
⚪ **LOW** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/36)) · Confidence: high (3/5 verifiers) · Effort: M · WS21

**Update (2026-07-10).** Fixed with [AUT-06](auth-security.md#aut-06): worker metrics WSGI app enforces Bearer `METRICS_TOKEN` when set.

**Locations:** `backend/app/core/metrics.py:102` (`start_metrics_server`); plus `backend/app/worker/celery_app.py:36`, `docker-compose.yml:76`.

**Evidence.** `start_metrics_server()` calls prometheus `start_http_server(port)` with no auth, while `main.py:49` gates the API `/metrics` behind `hmac.compare_digest(metrics_token)`. `docker-compose` publishes `'${METRICS_PORT:-9090}:9090'`, so the worker endpoint is reachable and unprotected.

**Failure scenario.** An operator sets `METRICS_TOKEN` expecting `/metrics` to be protected; the worker port stays wide open, exposing pipeline/scrape/notification counters to anyone who can reach the published port.

**Suggested fix.** Wrap the worker exposition in a small auth-checking handler honoring `metrics_token` (or bind it to loopback / document that it must be firewalled), matching the API path.

**Verification.** Confirmed 3/3 adversarial verifiers. `main.py:49` gates the API `/metrics` with `hmac.compare_digest(metrics_token)` but `start_metrics_server` calls `start_http_server(port)` with no auth, and docker-compose publishes the worker metrics port; unauthenticated counter exposure, low-sensitivity defense-in-depth.

<a id="xct-21"></a>
### XCT-21 — SSRF guard resolves DNS once; httpx re-resolves at connect (rebinding)
⚪ **LOW** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/37)) · Confidence: medium (3/5 verifiers) · Effort: M · WS21

**Update (2026-07-10).** Fixed with AUT-08 in [PR](https://github.com/davidcristian/HeadStart/pull/37): scrapers (httpx event hook), notifiers (`pinned_request`, including telegram), and Playwright route continues all connect via the IP from a single validated `getaddrinfo`, with Host/SNI preserved.

**Locations:** `backend/app/core/outbound_url.py:56` (`assert_safe_outbound_url`); plus `backend/app/scrapers/http.py:41`, `backend/app/notifiers/adapters/webhook.py:50`, `backend/app/notifiers/adapters/ntfy.py:48`, `backend/app/notifiers/adapters/telegram.py:35`.

**Evidence.** `assert_safe_outbound_url` does `getaddrinfo()` and IP-checks, but the subsequent httpx request re-resolves the hostname independently; a rebinding resolver can return a public IP on check and `169.254.169.254`/`127.0.0.1` on connect. The notifier clients also lack the scraper's per-request event hook.

**Failure scenario.** A user sets a source or webhook/ntfy target to a hostname under their control whose DNS flips to a private/metadata IP after the check, reaching internal services / cloud metadata.

**Suggested fix.** Pin the validated IP for the connection (resolve once, connect to that IP with a `Host` header), or use an httpx transport that enforces the allowlisted address; add the event-hook to the notifier clients.

**Verification.** Confirmed 3/3 adversarial verifiers. Real DNS-rebinding TOCTOU: the guard resolves via `getaddrinfo`, httpx re-resolves the hostname at connect; notifier clients lack the scraper's per-request hook; prior WS3 fixed `.localhost`/upfront checks, not rebinding. Low is fair.

<a id="xct-22"></a>
### XCT-22 — selectolax native C-ext on untrusted-HTML path: bus-factor / unpinned
⚪ **LOW** · ♻️ refactor · Status: ☐ open · Confidence: medium (3/5 verifiers) · Effort: S · WS15

**Locations:** `backend/pyproject.toml:23` (`selectolax`).

**Evidence.** `selectolax>=0.3.21` is the HTML parser on the untrusted-scraped-HTML path (AGENTS §7). It is a single-maintainer Modest/lolhtml C-extension; with no upper bound and no lock, an unvetted native-code release enters the untrusted-input parser automatically.

**Failure scenario.** If selectolax stalls (an unpatched parser CVE) or a malicious release is published, the scraper subsystem parsing attacker-influenced HTML has no pinned known-good version to fall back to and no SCA alert.

**Suggested fix.** Pin selectolax to a reviewed version with a hash in the lockfile; track upstream health and document a fallback parser (lxml) plan.

**Verification.** Confirmed 3/3 adversarial verifiers. `selectolax>=0.3.21` is unbounded, there is no lockfile (installed 0.4.10), and it parses untrusted HTML; the bus-factor angle is somewhat speculative, but unpinned-native-ext-on-untrusted-path is a valid low hardening finding.

<a id="xct-23"></a>
### XCT-23 — Manifest floors lag installed majors, hiding real support contract
⚪ **LOW** · 🔁 consistency · Status: ☐ open · Confidence: high (3/5 verifiers) · Effort: S · WS15

**Locations:** `backend/pyproject.toml:20` (`dependencies`).

**Evidence.** The installed venv resolves celery 5.6, redis 6.4 (major 6), stripe 15.3, cryptography 49, httpx 0.28 — but the floors say `celery>=5.4`, `redis>=5.0`, `stripe>=10.0`, `cryptography>=42.0`, `httpx>=0.27`. Code is tested only against the new majors; the low floors (stripe 10→15, redis 5→6 API breaks) are untested.

**Failure scenario.** A consumer honoring the stated floor installs stripe 10 / redis 5 and hits runtime `AttributeError`s the suite never covers, because CI runs against the newer resolved majors only.

**Suggested fix.** Bump the floors to the majors actually tested (`stripe>=15`, `redis>=6`, `celery>=5.6`) so the declared support matches reality; lock for builds.

**Verification.** Confirmed 3/3 adversarial verifiers. The installed venv (stripe 15.3, redis 6.4, cryptography 49, httpx 0.28) is a major ahead of the floors (stripe>=10, redis>=5, cryptography>=42); with no lockfile, the stated support contract is untested. Consistency, low is fair.

<a id="xct-24"></a>
### XCT-24 — No third-party dependency license inventory or NOTICE/attribution bundle
⚪ **LOW** · 📝 doc · Status: ☐ open · Confidence: high (3/5 verifiers) · Effort: S · WS39

**Locations:** `backend/pyproject.toml:10` (`dependencies`); plus `frontend/package.json:17`, `LICENSE:1`.

**Evidence.** No NOTICE/THIRD_PARTY_LICENSES file exists (`find -iname '*notice*'` hits only `.venv`). The backend bundles psycopg 3.3.4 (LGPL-3.0-only) plus BSD/MIT/Apache deps; the frontend ships React/react-router. No attribution manifest is maintained for conveyed artifacts.

**Failure scenario.** When the built frontend/backend images are conveyed (self-host per README:11), required upstream MIT/BSD/Apache/LGPL copyright notices are not preserved, breaching those licenses' attribution terms.

**Suggested fix.** Generate and commit a `THIRD_PARTY_LICENSES` manifest (pip-licenses + license-checker) and bundle it in the built artifacts.

**Verification.** Confirmed 3/3 adversarial verifiers. No NOTICE/THIRD_PARTY_LICENSES file exists (find hits only `.venv`/`node_modules`); the self-hostable project bundles MIT/BSD/Apache/LGPL deps whose attribution applies to conveyed artifacts. Valid low doc gap.

<a id="xct-25"></a>
### XCT-25 — Bundled LGPL-3.0 psycopg relink/source obligation not documented for self-host
⚪ **LOW** · 📝 doc · Status: ☐ open · Confidence: medium (2/3 verifiers) · Effort: XS · WS39

**Locations:** `backend/pyproject.toml:16` (`psycopg[binary]`); plus `frontend/package.json:17`.

**Evidence.** psycopg 3.3.4 + `psycopg_binary` METADATA report `License-Expression: LGPL-3.0-only`. It is bundled into the distributed backend image (README:11). LGPL-3.0 §4 requires enabling recipients to relink a modified library and providing the library source; no doc/NOTICE covers this.

**Failure scenario.** Conveying the backend container with LGPL psycopg without a corresponding-source/relink affordance breaches LGPL-3.0 §4 for downstream self-hosters.

**Suggested fix.** Document the LGPL psycopg dependency and its source/relink availability in the third-party notice; keeping it a pip dependency (not vendored) generally satisfies §4.

**Verification.** Confirmed 2/3 adversarial verifiers (1 refuted). psycopg/psycopg-binary metadata = LGPL-3.0-only, pinned in `pyproject.toml`, README markets distributed images, and no NOTICE/THIRD-PARTY file exists; real low-severity doc gap, though the §4 relink framing is mildly overstated for an unmodified pip dep.

<a id="xct-26"></a>
### XCT-26 — NTFY_DEFAULT_TOPIC defaults to guessable value and propagates to prod
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: high (3/5 verifiers) · Effort: XS · WS31

**Locations:** `devops/terraform/environments/prod/variables.tf:55` (`ntfy_default_topic`); plus `backend/app/core/config.py:167`, `.env.example:194`, `devops/terraform/environments/beta/terraform.tfvars.example:29`.

**Evidence.** The prod var default is `'headstart-change-me'` (`prod/variables.tf:55-58`), the stack pipes it to `NTFY_DEFAULT_TOPIC` (`stack/main.tf:163`), and the committed dev tfvars example hardcodes the same value. ntfy.sh topics are public/unauthenticated by name.

**Failure scenario.** An operator deploys without overriding the topic; the default notification target publishes job alerts to a public, guessable ntfy.sh topic anyone can subscribe to → low-sensitivity info leak.

**Suggested fix.** Make `ntfy_default_topic` required (no default) in prod, or randomize it; remove the placeholder from the tfvars example.

**Verification.** Confirmed 3/3 adversarial verifiers. `'headstart-change-me'` propagates `prod/variables.tf` → `stack/main.tf:163` → `NTFY_DEFAULT_TOPIC` and is committed in tfvars; the exploit is narrow (only `seed.py` demo uses it, not prod runtime), so low is right.

<a id="xct-27"></a>
### XCT-27 — useApplyToJob 'submitted' jobs-cache invalidation branch is unreachable (dead code)
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: high (3/5 verifiers) · Effort: S · WS41

**Locations:** `frontend/src/hooks/jobMutations.ts:46` (`useApplyToJob`); plus `backend/app/api/v1/jobs.py:120`, `frontend/src/components/ApplyJobDialog.tsx:139`, `frontend/src/hooks/jobMutations.test.tsx:79`.

**Evidence.** `onSuccess` only invalidates `['jobs']` when `result.status === 'submitted'`. But `POST /jobs/{id}/apply` always returns `status='queued'` for a live apply (`jobs.py:120`) and dry-runs return `'dry_run'`; the client never sees `'submitted'`, so this branch is dead.

**Failure scenario.** A live apply completes async in the worker; the jobs cache only refreshes because `ApplyJobDialog` invalidates `['jobs']` post-poll. The hook's own refresh never fires, so any non-dialog caller leaves the jobs list stale.

**Suggested fix.** Drop the unreachable `'submitted'` branch (rely on the post-poll invalidation), or move the jobs invalidation into the poll-completion path so all callers benefit.

**Verification.** Confirmed 3/3 adversarial verifiers. The live apply path always returns `status='queued'` (`jobs.py:120`); dry-run returns adapter `'dry_run'` status; adapters emit `'submitted'` only for synchronous non-dry applies which this endpoint never does, so the hook's `'submitted'` branch is dead.
