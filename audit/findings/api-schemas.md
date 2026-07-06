# API routers & Pydantic schemas

This area covers the FastAPI v1 routers under `backend/app/api/v1/` and the Pydantic request/response schemas under `backend/app/schemas/`. The audit found no correctness-critical defects: everything surfaced is medium or low. The two medium items are availability concerns — the resume/cover-letter generation and the manual "Run Now" search path both execute heavy, blocking work (LaTeX subprocess compile, LLM calls, rate-limited scrapes) inline in the request-serving threadpool, so a handful of concurrent callers can starve FastAPI's bounded anyio threadpool and stall unrelated endpoints. The remaining low findings are input-bounds bugs (out-of-bounds inbox `limit` producing HTTP 500 instead of 422), REST/error-shape consistency gaps (DELETE bodies, 200-vs-202, RSS bypassing central error handlers), schema drift (`portal_search` dropped from a response model), and defense-in-depth hardening (unbounded `answers` dict, unvalidated notifier `config`, unencoded OAuth error reflection).

**Summary:** 0 critical · 0 high · 2 medium · 10 low (14 confirmed findings, 2 dup pairs merged).

---

<a id="api-01"></a>
### API-01 — Sync LaTeX subprocess + LLM curation runs inline in generate-resume request
🟡 **MEDIUM** · ⚡ perf · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/58)) · Confidence: high (5/5 verifiers) · Effort: M · WS32

**Update (2026-07-10).** Fixed in [PR](https://github.com/davidcristian/HeadStart/pull/58): `POST /jobs/{id}/generate-resume` and `generate-cover-letter` enqueue `document_generation` rows and Celery tasks; clients poll `GET /document-generations/{id}` for the ready payload. LLM curation and LaTeX compile no longer run in the HTTP anyio threadpool.

**Locations:** `backend/app/api/v1/jobs.py:78` (`generate_resume`); plus `backend/app/services/resumes.py:88`, `backend/app/services/resumes.py:94`, `backend/app/resumes/compile.py:84`, `backend/app/api/v1/jobs.py:67`.

**Evidence.** The synchronous `def generate_resume` handler calls `ResumeService.generate()`, which runs an LLM curator and then `compile_latex` via `subprocess.run(timeout=60)`. FastAPI dispatches sync route handlers into a bounded anyio threadpool (~40 workers), so each call parks a worker for the full LLM round-trip plus up to 60s of `pdflatex`/`tectonic` compilation. `generate_cover_letter` has the identical shape.

**Failure scenario.** A handful of users hitting Generate Resume simultaneously exhausts the anyio threadpool; every other sync endpoint (login, list jobs) stalls behind the LaTeX compiles until they finish or hit the 60s timeout.

**Suggested fix.** Move resume/cover-letter generation to a Celery task (mirroring `apply_to_job`) returning an artifact id the UI polls, keeping the HTTP handler non-blocking.

**Verification.** Confirmed 5/5 adversarial verifiers. Sync `generate_resume` runs LLM curation + `subprocess.run(timeout=60)` in the bounded anyio threadpool with no rate limiting; concurrent calls can starve threads. This is a DoS/availability issue, which the rubric grades medium rather than high.

<a id="api-02"></a>
### API-02 — POST /searches/{id}/run runs the full scrape+summary pipeline synchronously
🟡 **MEDIUM** · ⚡ perf · Status: ☐ open · Confidence: high (5/5 verifiers) · Effort: M · WS32

**Locations:** `backend/app/api/v1/searches.py:54` (`run_search_now`); plus `backend/app/services/searches.py:83`, `backend/app/services/pipeline.py:80`.

**Evidence.** The synchronous `run_search_now` handler calls `SearchService.run_now` -> `PipelineService.run()`, which performs a rate-limited network scrape (`HttpClient.fetch`) followed by `SummaryService.annotate` (an LLM call), all inline in the HTTP handler. The scheduled worker path (`run_search`) is async via Celery, but this manual path is not.

**Failure scenario.** A user clicks Run Now on a slow or rate-limited source; the request holds a threadpool worker and DB session for the entire scrape+LLM duration (seconds to minutes), risking request timeouts and threadpool starvation under concurrent manual runs.

**Suggested fix.** Dispatch `run_search.delay(search_id)` and return 202 with a run handle the UI polls, mirroring the beat path; do not scrape inline in the request.

**Verification.** Confirmed 5/5 adversarial verifiers. `run_search_now` runs the full `PipelineService.run` (rate-limited scrape + LLM) inline in the request thread with no throttling — a real threadpool-starvation DoS, but the rubric places DoS at medium, so high would be inflated.

<a id="api-04"></a>
### API-04 — Out-of-bounds limit/seen_job_id on inbox list routes returns HTTP 500, not 422
🟡 **LOW** · 🐞 bug · Status: ☐ open · Confidence: certain (5/5 verifiers) · Effort: S · WS32

*(Merged: this is the same defect as reported under API-06 — out-of-bounds inbox `limit` producing an uncaught pydantic error. Both records cite `list_inbox_classifications` at inbox.py:227 with the same root cause; combined here.)*

**Locations:** `backend/app/api/v1/inbox.py:227` (`list_inbox_classifications`); plus `backend/app/api/v1/inbox.py:277`, `backend/app/api/v1/inbox.py:290`.

**Evidence.** These handlers accept a bare `limit: int = 50` (no `Query` bounds) and then re-validate it in-body via `EmailClassificationListParams(limit=limit)`, whose schema enforces `le=200` (and `ge=1` for `seen_job_id`). A value like `limit=201` or `limit=-1` raises a `pydantic.ValidationError` inside the handler. `main.py` registers a handler only for the unrelated `app.core.exceptions.ValidationError` class and has no catch-all, so the pydantic error escapes as an HTTP 500.

**Failure scenario.** `GET /inbox/classifications?limit=201` (or `?limit=-1`, or `/inbox/reply-drafts?seen_job_id=0`, or reply-send-logs) triggers an uncaught pydantic `ValidationError` -> HTTP 500, instead of the 422-with-field-detail every `Query`-bounded route returns.

**Suggested fix.** Declare these as `Query(default=50, ge=1, le=200)` (and `seen_job_id` as `Query(ge=1)`) like sibling routers, and drop the in-body `ListParams` re-validation.

**Verification.** Confirmed 5/5 adversarial verifiers (this merged pair; the lower-N record independently confirmed 3/3). Verified `EmailClassificationListParams(limit=201)` raises `pydantic.ValidationError` (not the app class), and `main.py` registers no handler for it, so it is uncaught. Any authenticated user can trigger it; low is fair.

<a id="api-03"></a>
### API-03 — GET /feed/rss uses local HTTPException, bypassing central error-shape handlers
⚪ **LOW** · 🔁 consistency · Status: ☐ open · Confidence: high (5/5 verifiers) · Effort: S · WS32

**Locations:** `backend/app/api/v1/feed.py:34` (`rss_feed`); plus feed.py:41.

**Evidence.** Domain errors normally flow through central exception handlers that yield a `{detail: ...}` shape, with `PlanLimitError` mapped to 402 with `code`/`plan`/`limit` fields (main.py:60-83). `rss_feed` re-implements this locally: it raises `HTTPException(401)` at :34 and manually re-maps `PlanLimitError` to `HTTPException(402)` at :41, instead of letting the registered handler run.

**Failure scenario.** The 402 body on `/feed/rss` loses the `code`/`plan`/`limit` fields the central handler adds (main.py:75-82), so this route's error shape silently diverges from every other plan-gated route.

**Suggested fix.** Let `PlanLimitError` propagate to the central handler (remove the local try/except) and use a domain exception for the invalid-token 401.

**Verification.** Confirmed 5/5 adversarial verifiers. `rss_feed` raises a local `HTTPException(401)` and remaps `PlanLimitError` to 402 (feed.py:34,41), bypassing the central handler (main.py:73-83) that adds `code`/`plan`/`limit`; a real low error-shape divergence.

<a id="api-05"></a>
### API-05 — OAuth callback reflects raw provider error query param unencoded into redirect URL
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: medium (2/3 verifiers) · Effort: XS · WS32

*(Merged: API-08 reports the identical defect — its verify_note states "Duplicate of uid 47." Both cover the same unencoded `error`-param reflection across the gmail/outlook/yahoo callbacks; combined here.)*

**Locations:** `backend/app/api/v1/inbox.py:86` (`gmail_oauth_callback`); plus `backend/app/api/v1/inbox.py:126` (outlook), `backend/app/api/v1/inbox.py:166`/`:167` (yahoo).

**Evidence.** The callback builds `url = f"{settings_url}?mailbox=gmail_error&reason={error}"`, interpolating the raw, attacker-influenceable `error` query param (the callback is unauthenticated) into the `Location` header without URL-encoding. The host is fixed to the trusted `frontend_base_url`, so this is not an open redirect, but the reflected value is unsanitized and extra params/fragments are injectable.

**Failure scenario.** An attacker crafts `/inbox/gmail/callback?error=<payload>`; the unencoded value is echoed into the redirect query string, enabling parameter-injection / query-smuggling / log-forging against the trusted frontend URL.

**Suggested fix.** URL-encode the reflected value via `urllib.parse.quote`, or map the provider error to a fixed allow-list of reason codes before interpolation.

**Verification.** Confirmed 2/3 adversarial verifiers (one refute; both records agree). The raw attacker-controllable `error` param is interpolated unencoded into a same-origin redirect, but the frontend only reads `mailbox`, not `reason`, so real impact is minimal param/log-injection hardening; low is fair.

<a id="api-07"></a>
### API-07 — Inbox/admin routes use unbounded raw query params instead of Query(ge,le) like siblings
⚪ **LOW** · 🔁 consistency · Status: ☐ open · Confidence: high (3/3 verifiers) · Effort: S · WS32

**Locations:** `backend/app/api/v1/inbox.py:198` (`fetch_mailbox_messages`); plus `backend/app/api/v1/inbox.py:202`, `backend/app/api/v1/inbox.py:221`, `backend/app/api/v1/inbox.py:271`, `backend/app/api/v1/admin.py:47`.

**Evidence.** `fetch_mailbox_messages` uses `since_uid: int | None, limit: int = 50` and clamps `limit` in-body while leaving `since_uid` unbounded; `admin.list_data_requests` uses `limit: int = 100` with `min(limit, 500)`. Every other router (jobs/applications/logs/feed) declares `Query(ge=1, le=500)`, so bounding is inconsistent across routers.

**Failure scenario.** A negative or huge `limit` or `since_uid` passes FastAPI validation and reaches the service/repo layer (e.g. `admin.list_data_requests` with a negative limit hits a DB `LIMIT`), diverging from peer routes' 422 behavior.

**Suggested fix.** Move all `limit`/`since_uid` bounds into `Query(..., ge=1, le=N)` so validation is uniform and documented in OpenAPI.

**Verification.** Confirmed 3/3 adversarial verifiers. Peer routes (jobs/applications/feed) use `Query(ge=1, le=500)` while inbox `fetch_mailbox_messages` and admin `list_data_requests` use raw unbounded params (`since_uid` unbounded, negative `limit` reaches DB `LIMIT`); a real consistency gap, low is fair.

<a id="api-09"></a>
### API-09 — List `limit` bounded via schema/min() not Query(ge,le); OpenAPI shows no bounds
⚪ **LOW** · 🔁 consistency · Status: ☐ open · Confidence: high (5/5 verifiers) · Effort: S · WS32

**Locations:** `backend/app/api/v1/inbox.py:224` (`list_inbox_classifications`); plus `backend/app/api/v1/inbox.py:202`, `backend/app/api/v1/inbox.py:272`, `backend/app/api/v1/inbox.py:286`, `backend/app/api/v1/admin.py:47`.

**Evidence.** jobs/applications/logs use `Query(default=100, ge=1, le=500)` (jobs.py:49). The inbox list routes declare a bare `limit: int = 50` then re-validate via `*ListParams` (:227, :290) or `min`/`max` (:206); `admin` data-requests uses `min()` (admin.py:47). The bounds are therefore invisible in OpenAPI and the caps diverge (200 vs 500). This is the same family of param-bounds inconsistency as API-07, but framed around OpenAPI visibility and cap divergence rather than runtime behavior.

**Failure scenario.** Generated OpenAPI/Swagger shows these `limit` params as unbounded ints, so client generators and docs cannot surface the real `ge`/`le` limits, and callers see inconsistent max caps across list resources.

**Suggested fix.** Standardize all list `limit` params on `Query(default=..., ge=1, le=...)` with one shared cap, and drop the schema/`min()` re-wrapping.

**Verification.** Confirmed 5/5 adversarial verifiers. inbox.py routes use bare `limit: int = 50` re-validated via `ListParams`/`min()` while jobs.py:49 uses `Query(ge=1, le=500)`; bounds are absent from OpenAPI and caps diverge — a real low consistency gap.

<a id="api-10"></a>
### API-10 — Live apply returns 200 `queued` for an async-accepted request instead of 202
⚪ **LOW** · 🔁 consistency · Status: ☐ open · Confidence: medium (5/5 verifiers) · Effort: S · WS32

**Locations:** `backend/app/api/v1/jobs.py:89` (`apply_to_job`); plus jobs.py:109-120.

**Evidence.** `POST /jobs/{id}/apply` enqueues a Celery task and returns `JobApplyResult(status='queued', application_log_id=...)` with the default 200 status (jobs.py:120). The request is accepted for asynchronous processing (client polls `GET /application-logs/{id}`) — the canonical 202 Accepted case — yet returns a synchronous 200.

**Failure scenario.** Clients cannot distinguish a completed synchronous apply from an accepted-but-pending one via status code; they must parse the body `status` field, weakening the REST contract for the async path.

**Suggested fix.** Return 202 for the enqueue (non-dry-run) path, keep 200 for dry-run, and document the distinction in `api.md`.

**Verification.** Confirmed 5/5 adversarial verifiers. `apply_to_job` enqueues a Celery task and returns `status='queued'` with default 200 (jobs.py:109-120) rather than 202 for the async path; a real low REST-contract nit.

<a id="api-11"></a>
### API-11 — DELETE /profile/resume(-template) return 200+body, breaking DELETE=204 convention
⚪ **LOW** · 🔁 consistency · Status: ☐ open · Confidence: high (5/5 verifiers) · Effort: S · WS32

**Locations:** `backend/app/api/v1/profile.py:69` (`delete_resume`); plus `backend/app/api/v1/profile.py:100` (`delete_resume_template`).

**Evidence.** Every other DELETE in the API returns 204 (sources.py:65, targets.py:48, credentials.py:47, profile.py:108, auth.py:150). But `DELETE /profile/resume` (:69) and `/profile/resume-template` (:100) return a `ProfileRead` body with the default 200. The frontend expects a body here (api/index.ts:284, :290), so it is intentional but inconsistent.

**Failure scenario.** A client generated from OpenAPI, or a developer following the 204-DELETE convention, mishandles the 200+`ProfileRead` body on these two DELETEs; the verb/status contract is non-uniform.

**Suggested fix.** Document these as state-returning DELETEs in `api.md`, or remodel them as POST/PATCH clear-actions to keep DELETE => 204 uniform.

**Verification.** Confirmed 5/5 adversarial verifiers. `delete_resume` (profile.py:69) and `delete_resume_template` (:100) return 200+`ProfileRead` while other DELETEs return 204; a genuine but intentional inconsistency, correctly low.

<a id="api-12"></a>
### API-12 — PlanFeaturesRead omits portal_search though snapshot() emits it
⚪ **LOW** · 🔁 consistency · Status: ✅ done · Confidence: high (3/3 verifiers) · Effort: XS · WS17

**Locations:** `backend/app/schemas/plan.py:22` (`PlanFeaturesRead`); plus plan_limits.py:83, health.py:32.

**Evidence.** `plan_limits.py` `snapshot()` builds a features dict that includes `portal_search` (plan_limits.py:83), and core `PlanFeatures` has the field, but `PlanFeaturesRead` lists only `digest_mode`/`ai_summaries`/`site_credentials`/`rss_feed` — `portal_search` is dropped from the typed response schema. `health.py:32` runs `AccountPlanRead.model_validate(snapshot)`, so the field is silently discarded.

**Failure scenario.** The `AccountPlanRead` response silently omits the `portal_search` flag, so the frontend cannot read it from the typed features object, risking client/server drift on Pro-only portal-search gating.

**Fix.** Add `portal_search: bool` to `PlanFeaturesRead` (same change as XCT-06) so the schema matches the snapshot payload. See [PR](https://github.com/davidcristian/HeadStart/pull/23).

**Verification.** Confirmed 3/3 adversarial verifiers. `snapshot()` emits `portal_search` (plan_limits.py:83) and `health.py:32` validates via `AccountPlanRead`, but `PlanFeaturesRead` lacks the field so it is dropped from the typed response; genuine schema drift, low is fair.

<a id="api-13"></a>
### API-13 — ProfileData.answers dict is unbounded unlike the capped skills list
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: medium (3/3 verifiers) · Effort: S · WS32

**Locations:** `backend/app/schemas/profile.py:94` (`ProfileData.answers`).

**Evidence.** `answers: dict[str, str] = Field(default_factory=dict)` has no size or per-value cap, while the sibling `skills` field is capped at 100 entries × 200 chars via `validate_skills`. The `answers` values are later embedded in apply payloads and LLM prompts, and no global request-size guard exists.

**Failure scenario.** A user PUTs a profile with thousands of huge answer values; the encrypted blob and every downstream apply/LLM payload bloat unbounded, inflating storage and prompt-token cost.

**Suggested fix.** Add a `field_validator` capping the `answers` key count and value length, mirroring `validate_skills`.

**Verification.** Confirmed 3/3 adversarial verifiers. `answers: dict[str, str]` has no cap while sibling `skills` and all string fields are `max_length`-bounded, and no global request-size guard exists, so it is genuinely unbounded — though self-inflicted; low input-bounds hardening is fair.

<a id="api-14"></a>
### API-14 — NotificationTarget config is free-form dict with no per-type validation
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: medium (5/5 verifiers) · Effort: M · WS32

**Locations:** `backend/app/schemas/target.py:11` (`TargetBase.config`); plus `backend/app/services/targets.py:31`, `backend/app/services/targets.py:39`.

**Evidence.** `TargetBase.config: dict[str, Any]` has no schema, and `TargetService.create`/`update` validate only the `type` field, never `config`. SSRF/`server_url` safety runs only inside `adapter.send`, and required keys (`topic`, `webhook_url`) surface as a `ValueError` at delivery time rather than on save.

**Failure scenario.** A target with a private/loopback `server_url` or a missing `topic` is accepted at write time; the failure only shows later as a silent failed `DeliveryResult`, with no write-time SSRF pre-check as defense-in-depth.

**Suggested fix.** Add per-type `config` validation (required keys + `assert_safe_outbound_url` on `server_url`/`webhook_url`) in `TargetService.create`/`update`.

**Verification.** Confirmed 5/5 adversarial verifiers. `TargetBase.config` is `dict[str, Any]` with no per-type validation; create/update only validate `type`. SSRF/required-key checks run at delivery inside the adapter, so this is legitimate defense-in-depth hardening, correctly rated low.
