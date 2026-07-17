# Documentation drift

This area covers correctness of the repository's prose: drift between the `docs/` module references (API surface, data model, notifiers, appliers, launch checklist) and the shipped code. The headline is that the audit found **no correctness bugs here — every finding is a low-severity documentation gap**, but the volume is notable: the canonical `api.md` endpoint table and `data-model.md` schema doc are materially incomplete, `launch-checklist.md` mis-states resume-upload automation and legal risk for LinkedIn/Indeed, `auth.md` has a truncated sentence.

**Summary by severity:** critical 0 · high 0 · medium 0 · low 15

After merging near-duplicate records (see the note at the end), 15 distinct findings survived adversarial verification. All are severity low / type doc.

---

<a id="doc-05"></a>
### DOC-05 — launch-checklist supported-adapters list omits 4 registered appliers
⚪ **LOW** · 📝 doc · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/129)) · Confidence: high (3/3 verifiers) · Effort: XS · WS25

**Locations:** `docs/launch-checklist.md:90` (`Auto-apply supported adapters`).

**Evidence.** 15 appliers are registered via `@register_applier`, including `smartrecruiters`, `shopify_careers`, `snowflake_careers`, and `uber_careers`. The checklist §7 "Supported adapters (v1)" (lines 90-94) lists only 11, dropping those four — all of which are documented in `appliers.md`.

**Failure scenario.** An operator preparing a hosted launch reads §7 to decide which auto-apply flows to test and skips SmartRecruiters/Uber/Shopify/Snowflake apply because the checklist does not list them as supported.

**Suggested fix.** Add SmartRecruiters, Uber, Shopify Careers, and Snowflake Careers to the launch-checklist §7 supported-adapters list.

**Verification.** Confirmed 3/3 adversarial verifiers. 15 appliers are @register_applier-registered but launch-checklist §7 (90-94) lists only 11, dropping smartrecruiters/shopify_careers/snowflake_careers/uber_careers; confirmed.

<a id="doc-11"></a>
### DOC-11 — api.md omits non-default success statuses (201 create, 204 webhook)
⚪ **LOW** · 📝 doc · Status: ✅ done · Confidence: medium (5/5 verifiers) · Effort: S · WS40

**Locations:** `docs/modules/api.md:84` (`status codes`).

**Evidence.** POST create routes return 201 (`sources.py:29`, `searches.py:21`, `targets.py:22`, `credentials.py:21`, `auth.py:58`, `admin.py:61`) and `POST /billing/webhook` returns 204 (`billing.py:59`), but the `api.md` endpoint table has no status column, so the 201/204 contract is undocumented.

**Failure scenario.** A client author assuming 200 for creates/webhook from the doc fails strict status assertions against the real 201/204 responses.

**Suggested fix.** Add a status-code note or column for create (201) and no-content (204) routes in `api.md`.

**Fix.** Annotate create rows and `POST /billing/webhook` with HTTP **201** / **204** in the v1 endpoint table, add a **Success status codes (DOC-11)** section covering 201/202/204 (and the profile resume DELETE 200 exceptions), and lock it with `test_doc11_success_statuses_api_md.py`. See [PR](https://github.com/davidcristian/HeadStart/pull/225).

**Verification.** Confirmed 5/5 adversarial verifiers. Verified code returns 201 for POST creates (sources/searches/targets/credentials/auth/admin) and 204 for delete/webhook, and docs/modules/api.md's route table has no status column — genuine minor doc drift.

<a id="doc-06"></a>
### DOC-06 — api.md endpoint table omits GET/PATCH /summary-preferences
⚪ **LOW** · 📝 doc · Status: ✅ done · Confidence: certain (3/3 verifiers) · Effort: XS · WS40

Merged: DOC-07 (uid 291) and DOC-10 (uid 299) reported the same defect and are folded in here.

**Locations:** `docs/modules/api.md:87` (`Endpoints table`); plus `backend/app/api/v1/__init__.py:48`, `backend/app/api/v1/summary_preferences.py:14`, `backend/app/api/v1/summary_preferences.py:21`.

**Evidence.** `api/v1/__init__.py:48` mounts `summary_preferences.router` at prefix `/summary-preferences` with `GET ''` and `PATCH ''` (`summary_preferences.py:14,21`), but `api.md`'s canonical v1 endpoint table (lines 16-88) lists no `/summary-preferences` rows. `summaries.md:57-58` does document them, proving `api.md` is the stale one.

**Failure scenario.** `api.md`, presented as the full v1 endpoint reference, is incomplete — a client author or agent using it as the index misses the per-user AI-preferences API and may re-add or mis-wire per-user AI provider config.

**Fix.** Add `GET /summary-preferences` and `PATCH /summary-preferences` rows to the `api.md` endpoint table (mirroring `summaries.md`). See [PR](https://github.com/davidcristian/HeadStart/pull/223).

**Verification.** Confirmed 3/3 adversarial verifiers. v1/__init__.py mounts summary_preferences at /summary-preferences (GET+PATCH); api.md endpoint table has zero references. Confirmed omission (three independent records converged on this).

<a id="doc-08"></a>
### DOC-08 — api.md profile section omits PUT/DELETE /profile/resume-template
⚪ **LOW** · 📝 doc · Status: ✅ done · Confidence: certain (3/3 verifiers) · Effort: XS · WS40

**Locations:** `docs/modules/api.md` (`profile endpoints`); plus `backend/app/api/v1/profile.py`.

**Evidence.** `PUT /resume-template` and `DELETE /resume-template` are live routes, but `api.md` previously listed only `/profile/resume`. `profile.md` already documented `resume-template`, so `api.md` alone was out of sync.

**Failure scenario.** A reader treating `api.md` as the full API map misses the LaTeX resume-template upload/delete endpoints used by the tailored-resume generation flow.

**Fix.** Add `PUT /profile/resume-template` and `DELETE /profile/resume-template` rows to `api.md` (shipped with API-11 state-returning DELETE docs). See [PR](https://github.com/davidcristian/HeadStart/pull/158).

**Verification.** Confirmed 3/3 adversarial verifiers. profile.py exposes PUT/DELETE /resume-template as live routes; api.md previously listed only /profile/resume — resume-template absent. Doc-drift, low is fair.

<a id="doc-09"></a>
### DOC-09 — api.md endpoint table omits the entire /inbox/* router (13+ routes)
⚪ **LOW** · 📝 doc · Status: ✅ done · Confidence: certain (3/3 verifiers) · Effort: S · WS40

**Locations:** `docs/modules/api.md:87` (`Endpoints table`).

**Evidence.** `api.md`'s endpoint table (lines 16-87) lists no `/inbox/*` route, yet `inbox.py` registers 18+ routes: credentials CRUD, gmail/outlook/yahoo authorize+callback, `/test`, `/messages`, `/classify`, `/classifications`, `/routing`, `/route`, `/draft-reply`, `/reply-drafts`, and `/reply-send-logs`.

**Failure scenario.** A developer reading the canonical API module doc has no reference for any inbox-automation route and must read source; the doc claims to enumerate v1 endpoints but is materially incomplete.

**Suggested fix.** Add an inbox section to the `api.md` endpoint table (or explicitly link `inbox.md`'s table as source of truth) and note dev-only gating.

**Fix.** Add `/inbox/*` rows to the `api.md` v1 endpoint table (credentials, OAuth authorize/callback, test/messages/classify/routing/reply routes), note `INBOX_AGENT_ENABLED`, and link [inbox.md](../../docs/modules/inbox.md) as the detailed source of truth; regression in `test_doc09_inbox_routes_api_md.py`. See [PR](https://github.com/davidcristian/HeadStart/pull/224).

**Verification.** Confirmed 3/3 adversarial verifiers. inbox.py registers 18+ /inbox/* routes; grep of api.md finds no inbox reference. Materially incomplete endpoint table, low fair.

<a id="doc-13"></a>
### DOC-13 — auth.md data-export sentence corrupted: dangling paren, dropped endpoint + list
⚪ **LOW** · 📝 doc · Status: ✅ done · Confidence: certain (3/3 verifiers) · Effort: XS · WS18

Merged: DOC-14 (uid 294) reported the same truncation and is folded in here.

**Fix.** Restored in the XCT-09 auth.md rewrite: sentence again names `GET /auth/me/export` and the full export contents.

<a id="doc-16"></a>
### DOC-16 — billing.md says "four public tiers" then lists only Starter, Plus, Pro
⚪ **LOW** · 📝 doc · Status: ✅ done · Confidence: high (3/3 verifiers) · Effort: XS · WS40

**Locations:** `docs/modules/billing.md:7` (`intro`).

**Evidence.** Line 7 reads "Stripe-powered subscriptions for the four public tiers (Starter, Plus, Pro)." The parenthetical lists three names; the fourth tier (Free) has no Stripe checkout, so the count and enumeration disagree. `user.py` confirms four plans (free/starter/plus/pro).

**Failure scenario.** A reader is confused whether there are three paid tiers or four; the number and the enumeration disagree in the billing doc's opening line.

**Suggested fix.** Reword to "the three paid tiers (Starter, Plus, Pro)" or "four tiers (Free, Starter, Plus, Pro)".

**Fix.** Intro now says "three paid tiers (Starter, Plus, Pro)" and points at the Plans table for the full Free/Starter/Plus/Pro matrix. Regression: `backend/tests/api/test_doc16_billing_tier_wording.py`. [PR](https://github.com/davidcristian/HeadStart/pull/226).

**Verification.** Confirmed 3/3 adversarial verifiers. billing.md:7 says "four public tiers (Starter, Plus, Pro)" — count says four, enumeration lists three; user.py confirms four plans. Internally inconsistent.

<a id="doc-17"></a>
### DOC-17 — data-model.md user table omits token_version + 4 AI-preference columns
⚪ **LOW** · 📝 doc · Status: ✅ done · Confidence: certain (3/3 verifiers) · Effort: S · WS40

Merged: DOC-18 (uid 233) reported the same omission and is folded in here.

**Locations:** `docs/modules/data-model.md:40` (`user entity table`); plus `backend/app/models/user.py:40`.

**Evidence.** `user.py` defines `token_version` (L40), `summary_provider` (L55), `summary_api_key_ciphertext` (L57), `ai_purpose_providers` (L59), and `ai_purpose_models` (L61). The `data-model.md` user table (lines 34-48), self-described as the schema source of truth, lists `feed_token_version` but none of these five real columns.

**Failure scenario.** An agent or developer consulting the canonical schema doc to reason about session revocation (`token_version`, WS13) or per-user AI keys builds against an incomplete model, missing security-relevant columns.

**Suggested fix.** Add `token_version` and the four AI-preference columns to the user table in `data-model.md`.

**Verification.** Confirmed 3/3 adversarial verifiers. user.py defines token_version(40), summary_provider(55), summary_api_key_ciphertext(57), ai_purpose_providers(59), ai_purpose_models(61) but data-model.md user table (34-48) lists only feed_token_version, omitting all five; certain doc drift (two independent records converged).

<a id="doc-19"></a>
### DOC-19 — data-model.md omits real tables (application_artifact, promo_*, data_request_log)
⚪ **LOW** · 📝 doc · Status: ✅ done · Confidence: high (3/3 verifiers) · Effort: S · WS40

**Locations:** `docs/modules/data-model.md:7` (`Entities`); plus `backend/app/models/application_artifact.py:22`, `backend/app/models/promo_redemption.py`, `backend/app/models/data_request_log.py`, `backend/app/models/application_log.py:30`.

**Evidence.** The models directory has `application_artifact` (user_id-owned), `promo_code`, `promo_redemption`, `promo_validation_attempt`, `data_request_log`, and `registration_lock` — none documented in `data-model.md`. Additionally, `application_log.py:30` has an `application_artifact` FK (`tailored_resume_artifact_id`) not shown in the `application_log` table (lines 225-234).

**Failure scenario.** `data-model.md` presents itself as the schema doc but silently omits user-owned tables (artifacts) and GDPR/billing tables, so a reader under-counts owned data and the export/erasure surface.

**Suggested fix.** Add sections (or an explicit "core entities only; see code for inbox/billing/GDPR tables" note) covering `application_artifact`, `promo_*`, and `data_request_log`; add the artifact FK to the `application_log` table.

**Verification.** Confirmed 3/3 adversarial verifiers. data-model.md Entities omits application_artifact, promo_*, data_request_log, registration_lock, inbox_* (all in models/), and the application_log table lacks the tailored_resume_artifact_id FK. Low fair.

<a id="doc-20"></a>
### DOC-20 — frontend.md says PWA opens on /jobs but start_url is /app/jobs
⚪ **LOW** · 📝 doc · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/229)) · Confidence: certain (3/3 verifiers) · Effort: XS · WS40

**Fix.** `docs/modules/frontend.md` Progressive Web App Install bullet now says the installed app opens on `/app/jobs`, matching `vite.config.ts` `start_url` and the routing section. Regression `test_doc20_frontend_pwa_start_url.py` locks both.

**Locations:** `docs/modules/frontend.md:166` (`Progressive Web App`).

**Evidence.** Line 166 says "The installed app opens on `/jobs` (`start_url` in the manifest)." But `vite.config.ts:20` sets `start_url: '/app/jobs'`, and `frontend.md:47` itself correctly cites `start_url: /app/jobs`. Line 166 is stale from before the `/app/*` migration and self-contradicts line 47.

**Failure scenario.** A reader believes the PWA launches at `/jobs`; that legacy path now only 301-redirects, so the documented behavior is wrong and internally inconsistent.

**Suggested fix.** Change `/jobs` to `/app/jobs` on line 166 to match `vite.config.ts` and line 47.

**Verification.** Confirmed 3/3 adversarial verifiers. frontend.md:166 says PWA opens on /jobs, but vite.config.ts:20 sets start_url:/app/jobs and frontend.md:47 itself cites /app/jobs; self-contradiction confirmed.

<a id="doc-21"></a>
### DOC-21 — frontend.md public-routes list omits the shipped /subprocessors route
⚪ **LOW** · 📝 doc · Status: ☐ open · Confidence: high (3/3 verifiers) · Effort: XS · WS40

**Locations:** `docs/modules/frontend.md:25` (`Routing: public site`).

**Evidence.** Line 25 enumerates public routes (`/`, `/pricing`, `/privacy`, `/terms`, `/impressum`, auth screens) but omits `/subprocessors`, a real public route (`App.tsx:51` `SubprocessorsPage`) and footer link (`PublicFooter.tsx:19`), also referenced by `auth.md:152` and launch-checklist §4.

**Failure scenario.** The frontend routing doc is an incomplete inventory of public pages; a reader auditing the public surface misses the GDPR subprocessors page.

**Suggested fix.** Add `/subprocessors` to the public routes list in `frontend.md` line 25.

**Verification.** Confirmed 3/3 adversarial verifiers. App.tsx:51 registers /subprocessors outside ProtectedRoute (a real public route) with PublicFooter.tsx:19 link, but frontend.md:25 public-routes list omits it.

<a id="doc-22"></a>
### DOC-22 — metrics.md implies METRICS_TOKEN guards /metrics, but worker :9090 has no auth
⚪ **LOW** · 📝 doc · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/36)) · Confidence: high (3/3 verifiers) · Effort: S · WS21

**Update (2026-07-10).** Closed with [AUT-06](auth-security.md#aut-06): worker honors `METRICS_TOKEN`, and `docs/modules/metrics.md` now states both scrape targets require Bearer auth when the token is set.

**Locations:** `docs/modules/metrics.md:54` (`Configuration / METRICS_TOKEN`).

**Evidence.** `metrics.md:54-56` says a token-set `/metrics` "requires Authorization: Bearer" and advises setting it for any internet-reachable deployment. Only `main.py:49-52` (the API route) checks the token; the worker uses `prometheus_client.start_http_server` (`metrics.py:102`), which is unauthenticated, so `:9090` serves metrics regardless of `METRICS_TOKEN`.

**Failure scenario.** An operator sets `METRICS_TOKEN` believing all `/metrics` endpoints are protected, then exposes worker `:9090` per the §8/AWS guidance; worker metrics (scrape volumes, adapters, enqueue counts) leak unauthenticated.

**Suggested fix.** Document that `METRICS_TOKEN` only guards the API `/metrics` route; the worker port needs network-level protection (security group / no public exposure).

**Verification.** Confirmed 3/3 adversarial verifiers. Only main.py:49-53 checks METRICS_TOKEN; worker metrics.py:96-102 uses raw prometheus_client start_http_server with no auth, yet metrics.md:54-64 implies the token guards /metrics and recommends exposing the worker port; low info-leak doc gap is fair.

<a id="doc-23"></a>
### DOC-23 — notifiers.md says ntfy uses URL-path + headers, but adapter POSTs JSON to server root
⚪ **LOW** · 📝 doc · Status: ☐ open · Confidence: high (3/3 verifiers) · Effort: XS · WS40

**Locations:** `docs/modules/notifiers.md:45` (`ntfy adapter section`).

**Evidence.** The doc says ntfy "POSTs to `{server_url}/{topic}` with headers Title/Priority/Tags/Click". The code instead POSTs to the server root with a JSON body carrying topic/title/priority/click/tags (`ntfy.py:82,100`). The doc also omits the optional bearer-token auth (`ntfy.py:118-120`).

**Failure scenario.** A maintainer debugging ntfy or writing an integration test follows the doc, expects path + header semantics, and is misled about the request shape and the token auth.

**Suggested fix.** Rewrite the ntfy section to describe the JSON-body publish to the server root and document the optional token auth.

**Verification.** Confirmed 3/3 adversarial verifiers. ntfy.py posts a JSON body (topic/title/priority/click/tags) to the server root (lines 82,110) and adds optional bearer token (118-120), but notifiers.md:45 documents POST to {server_url}/{topic} with headers and omits token auth; low doc drift is fair.

<a id="doc-03"></a>
### DOC-03 — launch-checklist: LinkedIn/Indeed resume upload "not automated" contradicts code
⚪ **LOW** · 📝 doc · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/128)) · Confidence: certain (3/3 verifiers) · Effort: XS · WS25

**Fix.** `docs/launch-checklist.md` §7 now states that Indeed-hosted live submit Base64-embeds `applicant.resume.file` and LinkedIn-hosted Easy Apply uploads via Ambry when a profile resume is stored (`resumeText` / plain text only as fallback). The Resume files row lists both adapters.

Merged: DOC-04 (uid 126) is a near-subset covering only the LinkedIn half and is folded in here.

**Locations:** `docs/launch-checklist.md:109` (`auto-apply portal table`); plus `docs/launch-checklist.md:108`, `backend/app/appliers/adapters/linkedin_resume_upload.py:37`, `backend/app/appliers/adapters/indeed_easy_apply.py:100`.

**Evidence.** Line 109 states "Resume PDF upload to LinkedIn is not automated in v1"; line 108 states Indeed "resume PDF upload is not automated … (resumeText fallback only)". But `upload_easy_apply_resume()` PUTs the file to Ambry (`linkedin.py:180`) and `build_submit_body` base64-embeds `applicant.resume.file` bytes with `resumeText` only as a fallback (`indeed_easy_apply.py:100`); `test_indeed_resume.py` asserts this. `appliers.md:594-597` also documents LinkedIn upload as automated, so the checklist rows are the stale ones.

**Failure scenario.** An operator reading the checklist believes no resume file leaves the platform for LinkedIn/Indeed and skips DPA/privacy review of that data flow, mis-stating processing to users/regulators.

**Suggested fix.** Update both launch-checklist rows to state that LinkedIn (Ambry) and Indeed-hosted live submit DO upload the stored resume file bytes; mirror the wording in `docs/modules/appliers.md`.

**Verification.** Confirmed 3/3 adversarial verifiers. linkedin.py:180 calls upload_easy_apply_resume (PUTs bytes to Ambry) and indeed build_submit_body:100 base64-embeds resume bytes with resumeText only as fallback; checklist lines 108-109 "not automated" contradict shipped code (two records converged, one a subset).

<a id="doc-12"></a>
### DOC-12 — No ToS/legal-risk disclosure for LinkedIn Voyager & Indeed smartapply automation
⚪ **LOW** · 📝 doc · Status: ✅ done · Confidence: medium (3/3 verifiers) · Effort: S · WS25

**Update (2026-07-11).** Closed in [PR](https://github.com/davidcristian/HeadStart/pull/130): `appliers.md` Safety & consent and launch-checklist §7 Safety now state that LinkedIn Voyager / Indeed smartapply cookie automation typically breaches those platforms' User Agreements, is at operator/user own risk, and requires `accept_private_api_risk` (APL-17 gating). Related scrape-side disclosure remains [XCT-19](cross-cutting.md#xct-19).

**Locations:** `docs/modules/appliers.md` (`Safety & consent`); plus `docs/launch-checklist.md` §7 Safety.

**Evidence.** The LinkedIn and Indeed adapters drive private Voyager GraphQL (`linkedin_voyager.py`) and smartapply (`indeed_easy_apply.py:12`) using the user's own session cookies — automated access that both platforms' User Agreements prohibit. The "Safety & consent" section and the launch checklist document only functional limits, never the ToS/legal risk; grep found no ToS/User-Agreement/legal-risk warning in either.

**Failure scenario.** An operator ships auto-apply on LinkedIn/Indeed unaware it breaches those platforms' terms; user accounts get restricted/banned and the operator faces takedown/legal exposure with no warning in the docs.

**Suggested fix.** Add a compliance note in "Safety & consent" and the launch checklist stating that LinkedIn/Indeed self-cookie automation violates their ToS and is at the operator/user's own risk.

**Verification.** Confirmed 3/3 adversarial verifiers. Confirmed LinkedIn Voyager and Indeed smartapply automation via users' own cookies; grep found no ToS/User-Agreement/legal-risk warning in appliers.md Safety & consent or launch-checklist — valid low doc/compliance gap.

<a id="doc-15"></a>
### DOC-15 — auth.md "everything they own" export omits apply logs, artifacts, inbox data
⚪ **LOW** · 📝 doc · Status: ✅ done · Confidence: high (3/3 verifiers) · Effort: M · WS18

**Fix.** Closed with XCT-09: export now includes the previously omitted entities, and auth.md lists them explicitly.

---

<a id="doc-24"></a>
### DOC-24 — AGENTS.md §6 understates the frontend coverage exclusions (self-declared DoD violation)
⚪ **LOW** · 📝 doc · Status: ☐ open · Confidence: high (delta audit) · Effort: S · WS42

**Locations:** `AGENTS.md` §6 (Quality bars — frontend).

**Evidence.** §6 states "Only `src/types/**` and `*.d.ts` are excluded", but `frontend/vite.config.ts` now excludes five patterns: `src/types/**`, `**/*.d.ts`, `**/*.test.{ts,tsx}`, `src/main.tsx`, `src/test/**`. Commit `702808e` added `src/main.tsx` + `src/test/**` and updated AGENTS.md §3 but left §6 stale — which §0/§5 ("stale docs are a bug") call a Definition-of-Done violation.

**Failure scenario.** A reader trusts §6 and assumes new `main.tsx` logic or a new `src/test/**` helper is gate-enforced; it is not. No product code lost coverage today (`main.tsx` is branchless bootstrap; `src/test/**` has no product importer), so impact is false assurance only.

**Suggested fix.** Update §6 to list the five actual exclusions (the config comment at `vite.config.ts:64-66` is already accurate).

**Verification.** Confirmed 3/3 verifiers (delta audit, 2026-07-03); all voted low severity — genuine doc drift, no gate-integrity loss.

---

<a id="doc-25"></a>
### DOC-25 — README lists `ntfy` in the `make up` service set, but `make up` never starts it
⚪ **LOW** · 📝 doc · Status: ☐ open · Confidence: high (delta audit) · Effort: S · WS42

**Locations:** `README.md:93` (quick-start `make up` comment).

**Evidence.** The README restyle changed the comment to `# api, worker, beat, db, redis, frontend, ntfy`, but `ntfy` is declared `profiles: ["offline"]` in `docker-compose.yml:112`, and `make up` → `scripts/dev.sh up` runs `compose up -d --build` with no `--profile offline`. Compose skips profile-gated services, so `make up` starts everything except `ntfy`.

**Failure scenario.** A new user runs `make up`, expects a self-hosted ntfy server per the README, and finds none at `:8090`. Onboarding confusion; no security impact.

**Suggested fix.** Drop `, ntfy` from the line, or annotate it as requiring `--profile offline`.

**Verification.** Confirmed (delta audit, 2026-07-03). The compose header itself documents ntfy as opt-in via `--profile offline`.
