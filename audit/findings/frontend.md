# Frontend — React app, data layer, components, a11y

This document covers the React/TypeScript single-page app in `frontend/`: the auth
context and route guards, the fetch-based API client and React Query data layer,
shared UI components and profile/settings forms, the nginx static-serving
container, the legal/GDPR pages, and accessibility (WCAG) across dialogs, forms
and navigation. The headline: no critical or high-severity defects survived
verification, but there is a consistent cluster of real issues — a cross-user
React Query cache leak on shared browsers, `javascript:` URL XSS from scraped job
links rendered into `href`, several GDPR/privacy-disclosure drifts (understated AI
data flows, undisclosed subprocessors, missing lawful basis, incomplete
retention), a portals default-selection that 422s the happy path, and a broad set
of low-severity accessibility gaps (missing live regions, skip link, focus
management, form labels) plus assorted correctness/consistency nits.

**Summary:** 🔴 critical: 0 · 🟠 high: 0 · 🟡 medium: 6 · ⚪ low: 32 (39 records; FRO-01/FRO-02, FRO-08/FRO-09, and FRO-13/FRO-15 each merged as duplicate pairs).

---

<a id="fro-01"></a>
### FRO-01 — Logout/login never clear React Query cache; previous user's PII survives into next session
🟡 **MEDIUM** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/21)) · Confidence: high (5/5 verifiers) · Effort: S · WS16

_Merged with FRO-02 — both records describe the same defect: the module-level `queryClient` is never cleared on an SPA session switch._

**Update.** Fixed in [PR](https://github.com/davidcristian/HeadStart/pull/21): `AuthProvider` calls `queryClient.clear()` on successful `login`, on `logout`, and when the API client's unauthorized handler fires (hard 401 after refresh failure), so a shared-browser session switch cannot serve the previous account's cached PII.

**Locations:** `frontend/src/auth/AuthContext.tsx:31` (`logout`); plus `frontend/src/auth/AuthContext.tsx:65` (`login`), `frontend/src/main.tsx:13` / `frontend/src/main.tsx:22` (module-level `queryClient`), `frontend/src/pages/LoginPage.tsx:30`, `frontend/src/components/Layout.tsx:81`.

**Evidence.** `logout()` only calls `api.logout()`, `clearAccessToken()`, and `setUser(null)`; `login()` only sets the access token and user. Neither touches the module-level `queryClient` created in `main.tsx` (a grep for `useQueryClient` / `clear` / `removeQueries` in `src/auth` and `Layout` returns nothing). Cached queries are keyed by resource (sources/searches/credentials/profile/jobs/applications), not by user, and the client persists across an SPA logout→login with no page reload and a `staleTime` of 10s.

**Failure scenario.** On a shared or kiosk browser, User A logs out and User B logs in via client-side navigation (no reload). Until each query refetches, React Query serves A's cached credentials/profile/jobs/applications PII into B's screens — cross-user data exposure.

**Suggested fix.** Call `queryClient.clear()` / `removeQueries` (via `useQueryClient`) inside `logout` and on successful `login` (or in the unauthorized handler) so no cross-user cache survives the session switch.

**Verification.** Confirmed 5/5 adversarial verifiers. Real cache leak: `queryClient` is never cleared on a session switch and keys are not user-scoped; graded medium because exposure is gated on a shared browser + no-reload re-login and lasts only until refetch.

<a id="fro-03"></a>
### FRO-03 — Scraped job URLs rendered into href with no scheme allow-list (javascript: XSS)
🟡 **MEDIUM** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/22)) · Confidence: high (5/5 verifiers) · Effort: S · WS16

**Update (2026-07-10).** Fixed: shared `safeHref()` allows only `http`/`https`; the five scraped-URL anchors render plain text when the scheme is unsafe — [PR](https://github.com/davidcristian/HeadStart/pull/22).

**Locations:** `frontend/src/components/JobList.tsx:134` (`JobTitle`); plus `frontend/src/components/ApplicationPipelineList.tsx:164`, `frontend/src/pages/portals/PortalsResultsCard.tsx:38`, `frontend/src/components/SearchHealth.tsx:55`, `frontend/src/components/profile/ApplicationHistoryTable.tsx:44`.

**Evidence.** `<a href={job.url}>` renders scraped URLs verbatim at five sites. `job.url` is a plain `str` (`schemas/job.py:22`) sourced from raw upstream JSON (`lever.py:96` hostedUrl, `ashby_parse.py:56` jobUrl, `greenhouse.py:48` absolute_url, generic_html href — where `_href` does a `urljoin` that preserves a scraped `javascript:` href). No scheme guard exists anywhere (no `sanitizeUrl` / `javascript:` check in the schema or at any `<a href={...}>`), and React does not sanitize `href`.

**Failure scenario.** A compromised, typo-squatted, or generic_html source emits `url: "javascript:..."`; the user clicks the job title in Jobs, Applications, or Portals and arbitrary script runs in the victim's authenticated session.

**Suggested fix.** Add a shared safe-URL helper permitting only `http`/`https` (and `mailto`) at every scraped-URL `<a>`, or reject non-`http(s)` job URLs at scrape/store time in the backend.

**Verification.** Confirmed 5/5 adversarial verifiers. Real DOM XSS on click; medium given the attacker-controlled-source and user-click preconditions.

<a id="fro-04"></a>
### FRO-04 — Privacy policy understates AI data: resume/profile PII and recruiter emails sent
🟡 **MEDIUM** · 📝 doc · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/26)) · Confidence: high (3/5 verifiers) · Effort: S · WS18

**Update (2026-07-10).** Fixed in [PR](https://github.com/davidcristian/HeadStart/pull/26): `/privacy` now discloses purpose-specific AI data categories (match summaries; cover letters / resume curation with profile PII and resume excerpts; email classification; reply drafting with recruiter message + contact details).

**Locations:** `frontend/src/pages/PrivacyPolicyPage.tsx:78` (`PrivacyPolicyPage`).

**Evidence.** The policy states AI providers receive "only the job title, company, location, and filter context." In reality the `cover_letters`, `resumes`, and `reply_drafters` adapters send the application profile (resume text, contact details) and recruiter subject/body to the same LLM providers. `reply_drafters/prompts.py` sends name/email/phone plus the recruiter `inbound_body`, and `CoverLetterContext` sends full `ProfileData` to OpenAI/Anthropic/Gemini.

**Failure scenario.** A user relies on the stated limited disclosure; in reality their resume, contact info, and recruiters' email content are transmitted to OpenAI/Gemini/Anthropic, contradicting the policy.

**Suggested fix.** Describe all AI purposes (summaries, cover letters, resume curation, reply drafting, email classification) and the categories of PII each sends.

**Verification.** Confirmed 3/3 adversarial verifiers. Understatement confirmed against the actual prompt/context builders.

<a id="fro-05"></a>
### FRO-05 — No lawful-basis/consent record for auto-apply sending PII to job boards
🟡 **MEDIUM** · 📝 doc · Status: ✅ done · [PR](https://github.com/davidcristian/HeadStart/pull/27)

**Update (2026-07-10).** Privacy policy now discloses auto-apply PII flows and lawful basis (consent). `ApplyService` stamps `user_consent` on every `application_log` payload (`basis`, `mechanism`, `live_submission`, `recorded_at`); queue-time consent is preserved when a queued log is finalized.

**Locations:** `frontend/src/pages/PrivacyPolicyPage.tsx:60` (`PrivacyPolicyPage`).

**Evidence.** The privacy "Third parties" list covers job boards "for scraping only"; it never states that auto-apply transmits the user's name/contact/resume to career sites on their behalf, nor a lawful basis. No stored consent/opt-in record model exists for auto-apply — the only "consent" code is job-board terms acceptance, not a persisted HeadStart opt-in artifact.

**Failure scenario.** Auto-apply sends full application PII to Greenhouse/Lever/Workday etc.; the privacy policy discloses only scraping, and there is no persisted consent artifact evidencing the user authorized each submission.

**Suggested fix.** Disclose auto-apply data flows and lawful basis in the privacy policy, and persist an auditable per-submission consent/opt-in record.

**Verification.** Confirmed 3/3 adversarial verifiers. Disclosure/lawful-basis gap holds; appliers send full PII to career sites with no persisted opt-in artifact.

<a id="fro-06"></a>
### FRO-06 — Subprocessor list omits shipped Gemini/Anthropic AI and mailbox providers
🟡 **MEDIUM** · 📝 doc · Status: ✅ done · Confidence: high (3/5 verifiers) · Effort: S · WS18

**Locations:** `frontend/src/pages/SubprocessorsPage.tsx:8` (`SUBPROCESSORS`).

**Evidence.** `SUBPROCESSORS` lists only AWS/Stripe/OpenAI/SMTP. But `gemini.py` and `anthropic.py` adapters ship for summarizers/cover_letters/resumes/reply_drafters/email_classifiers, and Gmail/Outlook/Yahoo OAuth inbox adapters process mailbox content — none of these are disclosed.

**Failure scenario.** An operator enables Gemini/Anthropic or the inbox agent; personal data (profile, recruiter emails) flows to Google/Anthropic/mail providers not named in the Art.28 subprocessor list, breaching the disclosure duty.

**Suggested fix.** Add Google (Gemini), Anthropic, and inbox mail/OAuth providers to the subprocessor table with purpose/data/location, or gate the list to the enabled providers.

**Verification.** Confirmed 3/3 adversarial verifiers. Real Art.28 gap: the shipped AI and inbox adapters exist but the list names only AWS/Stripe/OpenAI/SMTP.

<a id="fro-07"></a>
### FRO-07 — Portals default all-selected exceeds backend portal_ids cap of 30, Search/Subscribe 422s
🟡 **MEDIUM** · 🐞 bug · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/78)) · Confidence: high (3/5 verifiers) · Effort: S · WS41

**Update (2026-07-10).** Company search caps selection at 30 (`MAX_PORTAL_SELECTION` / `capPortalIds`): default load and Select-all take the first 30 in catalog order, toggles refuse adds at the cap, and unselected checkboxes disable when full — [PR](https://github.com/davidcristian/HeadStart/pull/78).

**Locations:** `frontend/src/pages/portals/usePortalsPage.ts:48` (`usePortalsPage effect / runSearch / createAlerts`); plus `frontend/src/pages/portals/PortalsSearchCard.tsx:109`, `backend/app/schemas/portal.py:36`, `backend/app/schemas/portal.py:72`.

**Evidence.** The effect `setSelectedIds(new Set(catalogItems.map(p => p.id)))` selects the whole allowed catalog. For Pro, `scraper_allowed()` is `True` for every preset (~41 in `portals/presets/`), so "All" picks ~41. `runSearch`/`createAlerts` POST `portal_ids=[...selectedIds]`, but `portal.py` caps `portal_ids` at `max_length=30`. Neither the hook nor `PortalsSearchCard` caps the selection.

**Failure scenario.** A Pro user (the only tier with portal search) opens Company search, keeps the default all-selected state, clicks Search jobs / Create alerts, and gets a 422 error banner; the happy path is broken until they manually deselect below 30.

**Suggested fix.** Cap selection at 30 client-side (disable extra checkboxes / Select-all), surface the 30-portal limit, and validate size before the mutation.

**Verification.** Confirmed 3/3 adversarial verifiers. ~41 presets all pass `scraper_allowed`; the effect default-selects the full catalog and nothing caps at 30, so both `portal_id` schemas (`max_length=30`) 422 on the happy path.

---

<a id="fro-08"></a>
### FRO-08 — Frontend nginx container runs as root (no USER directive)
⚪ **LOW** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/97)) · Confidence: high (3/5 verifiers) · Effort: M · WS20

_Merged with FRO-09 — both records describe the same defect: the nginx runtime stage sets no `USER`._

**Update (2026-07-10).** Fixed: runtime image is `nginxinc/nginx-unprivileged:1.27-alpine` (non-root `nginx` user), `nginx.conf` listens on **8080**, and compose / ECS / ALB target group / tasks-SG ingress target 8080 instead of privileged :80 — [PR](https://github.com/davidcristian/HeadStart/pull/97).
**Locations:** `frontend/Dockerfile:15` (runtime stage).

**Evidence.** The runtime stage `FROM nginx:1.27-alpine` sets no `USER`; the stock nginx image starts its master process as root (only workers drop to `nginx`). The backend image carefully creates `appuser` (uid 10001) and runs `USER appuser`, so this is an asymmetric hardening gap.

**Failure scenario.** An RCE in nginx or a mounted-path traversal executes with root inside the container, widening the blast radius (write to any bind-mount, easier container escape) versus an unprivileged process.

**Suggested fix.** Use `nginxinc/nginx-unprivileged` or add a non-root user, chown `/usr/share/nginx/html` + `/var/cache/nginx`, listen on a port >1024, and set `USER`.

**Verification.** Confirmed 3/3 adversarial verifiers. Real divergence from the repo's non-root posture; nginx serves static files only (no proxy_pass) and workers drop to the nginx user, so this is defense-in-depth hardening = low.

<a id="fro-20"></a>
### FRO-20 — Partner-ad iframe sandbox allows both allow-scripts and allow-same-origin
⚪ **LOW** · 🔒 security · Status: ✅ done · Confidence: medium (3/5 verifiers) · Effort: S · WS20

**Update (2026-07-10).** Fixed: partner `FreeTierAd` iframe sandbox is `allow-scripts allow-popups` only (no `allow-same-origin`), so a same-origin or open-redirect slot cannot lift its sandbox and script the parent app — [PR](https://github.com/davidcristian/HeadStart/pull/105).

**Locations:** `frontend/src/components/FreeTierAd.tsx:51` (`FreeTierAd`).

**Evidence.** `sandbox="allow-scripts allow-same-origin allow-popups"` on the external ad iframe. Combining `allow-scripts` + `allow-same-origin` lets same-origin framed content remove its own sandbox; effective only if `external_slot_url` is ever same-origin, but a documented anti-pattern for untrusted embeds.

**Failure scenario.** If `external_slot_url` is served same-origin (or via an open redirect on the origin), the framed ad can script the parent app; consent-gated but operator-configured.

**Suggested fix.** Drop `allow-same-origin` for third-party ad frames, or ensure the slot is always cross-origin and restrict it via a CSP `frame-src`.

**Verification.** Confirmed 3/3 adversarial verifiers. The sandbox anti-pattern is real defense-in-depth; consent-gating and the cross-origin precondition limit impact, so low.

<a id="fro-11"></a>
### FRO-11 — nginx serves SPA without any security response headers
⚪ **LOW** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/35)) · Confidence: high (3/5 verifiers) · Effort: S · WS20

**Update (2026-07-10).** Fixed with [XCT-16](cross-cutting.md#xct-16): production nginx emits CSP / framing / HSTS / nosniff / Referrer-Policy / Permissions-Policy on the SPA shell — [PR](https://github.com/davidcristian/HeadStart/pull/35).

**Locations:** `frontend/nginx.conf:1` (server block).

**Evidence.** `nginx.conf` adds only Cache-Control headers. There is no Content-Security-Policy, X-Frame-Options/`frame-ancestors`, Strict-Transport-Security, X-Content-Type-Options, or Referrer-Policy on the HTML that renders the authenticated app, and the Terraform ALB module injects no response headers either.

**Failure scenario.** The app can be framed (clickjacking), MIME-sniffed, and lacks CSP defense-in-depth against injected scripts; HTTPS deployments miss HSTS. Exploitable if any XSS/clickjacking primitive is found in the SPA.

**Suggested fix.** Add `add_header` for `X-Content-Type-Options nosniff`, a `frame-ancestors` CSP (or `X-Frame-Options DENY`), `Referrer-Policy`, and HSTS on the TLS edge.

**Verification.** Confirmed 3/3 adversarial verifiers. No CSP/X-Frame/HSTS/nosniff in `nginx.conf` or the ALB module; a real defense-in-depth gap, low.

<a id="fro-10"></a>
### FRO-10 — index.html served with no Cache-Control while assets are immutable
⚪ **LOW** · 🐞 bug · Status: ✅ done · Confidence: medium (3/5 verifiers) · Effort: XS · WS20

**Update (2026-07-10).** Fixed: `location /` sets `Cache-Control: no-cache` so the SPA HTML shell revalidates after deploy while `/assets/` stay `public, immutable` — [PR](https://github.com/davidcristian/HeadStart/pull/98).

**Locations:** `frontend/nginx.conf:19` (`location /`).

**Evidence.** `location /assets/` sets `expires 1y immutable` (lines 8–11); `sw.js`/`manifest` get `no-cache` (14–17); but `location /` (20–22) serving `index.html` sets no Cache-Control, so browsers/CDNs may heuristically cache the HTML shell that references hashed assets. No upstream/edge cache-header injection exists in the ALB Terraform.

**Failure scenario.** After a deploy, a returning visitor gets a cached `index.html` pointing at old asset hashes that nginx no longer has (immutable assets replaced) → 404s / blank app until a hard refresh.

**Suggested fix.** Add an explicit `add_header Cache-Control "no-cache"` for `index.html` in the `location /` block.

**Verification.** Confirmed 3/3 adversarial verifiers. Heuristic HTML caching after deploy is a real PWA hazard.

<a id="fro-12"></a>
### FRO-12 — vite-plugin-pwa/vite chain locks esbuild 0.21.5 (dev-server SSRF)
⚪ **LOW** · 🔒 security · Status: ✅ done · Confidence: medium (3/5 verifiers) · Effort: S · WS20

**Update (2026-07-10).** Fixed: vite ^6.4.3 + `overrides.esbuild: ^0.25.0` (lockfile **0.25.12**), vitest 3.2.7+, CI `just audit-frontend`, and Dependabot for `frontend/` — [PR](https://github.com/davidcristian/HeadStart/pull/99).

**Locations:** `frontend/package.json:39` (`devDependencies.vite-plugin-pwa`).

**Evidence.** `'vite-plugin-pwa':'^1.3.0'` + `'vite':'^5.4.3'` resolve (per lockfile) to esbuild 0.21.5, which predates the GHSA-67mh-4wv8-2f99 dev-server SSRF fix (patched 0.25.0). The carets also drag in workbox-build 7.4.1 / rollup 4.62. Dev/build-only. No `npm audit` or Dependabot is wired into CI.

**Failure scenario.** esbuild <0.25's dev server lets any website the developer visits send requests to it and read the responses (GHSA-67mh-4wv8-2f99), leaking source while `vite dev` runs. Build-time only, low blast radius.

**Suggested fix.** Bump the vite/esbuild chain (vite ≥5.4.15 pulls esbuild ≥0.25), add `npm audit` to CI, and enable Dependabot for the frontend lockfile.

**Verification.** Confirmed 3/3 adversarial verifiers. Lockfile pins esbuild 0.21.5; dev/build-only, correctly rated low.

<a id="fro-13"></a>
### FRO-13 — 401 refresh has no in-flight dedup: concurrent requests fire N parallel refresh POSTs
⚪ **LOW** · 🐞 bug · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/232)) · Confidence: high (3/5 verifiers) · Effort: S · WS41

_Merged with FRO-15 — both records describe the same defect: no single-flight guard on the 401 refresh path._

**Update.** Fixed: `refreshSession` holds one module-level in-flight promise so concurrent 401s from `request` / `requestForm` / `requestBlob` await a single `POST /auth/refresh`, then all retry — [PR](https://github.com/davidcristian/HeadStart/pull/232).
**Locations:** `frontend/src/api/client.ts:55` (`refreshSession`); plus the three callers `frontend/src/api/client.ts:100` (`request`), `:121` (`requestForm`), `:147` (`requestBlob`).

**Evidence.** `request`/`requestForm`/`requestBlob` each call `refreshSession()` independently on a 401 with no shared in-flight promise. On token expiry, every simultaneous query triggers its own `POST /auth/refresh`. The backend rotates the cookie each time (`auth.py:79`) without single-use revocation and does not bump `token_version`, so all succeed but race.

**Failure scenario.** After the access token expires, a page mounting several `useQuery` hooks fires N parallel refresh calls; the last cookie write wins and earlier requests race, wasting server round-trips (refresh storm). Harmless today only because refresh does not rotate `token_version`; if rotation is added, concurrent refreshes would race and log sessions out.

**Suggested fix.** Memoize a single module-level in-flight refresh promise so concurrent 401s await one refresh, then all retry; reset it once settled.

**Verification.** Confirmed 3/3 adversarial verifiers. The three callers each refresh independently and the backend refresh does not revoke/rotate `token_version`, so N parallel 401s fire N refresh POSTs; correctly low (no current harm).

<a id="fro-14"></a>
### FRO-14 — parse() throws raw SyntaxError on malformed 2xx body instead of ApiError
⚪ **LOW** · 🐞 bug · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/233)) · Confidence: medium (3/5 verifiers) · Effort: XS · WS41

**Locations:** `frontend/src/api/client.ts:69` (`parse`).

**Evidence.** `const data = text ? JSON.parse(text) : undefined;` is unguarded. A 200 with a non-JSON body (proxy/CDN error page, truncated payload) makes `JSON.parse` throw a `SyntaxError`, bypassing `ApiError` normalization. `requestBlob` (lines 160–164) wraps the same parse in try/catch; `request`/`requestForm` do not.

**Failure scenario.** A misbehaving gateway returns HTML with a 200 status; callers and UI error boundaries receive an opaque "Unexpected token <" `SyntaxError` instead of an `ApiError` with a usable status/message.

**Suggested fix.** Wrap the `JSON.parse` in try/catch and throw `ApiError(resp.status, text || statusText)` on failure, mirroring `requestBlob`.

**Verification.** Confirmed 3/3 adversarial verifiers. Minor error-handling inconsistency, low.

<a id="fro-16"></a>
### FRO-16 — refreshSession does not guard resp.json()/network errors, bypassing graceful 401->login
⚪ **LOW** · 🐞 bug · Status: ✅ done · Confidence: medium (3/5 verifiers) · Effort: XS · WS41

**Locations:** `frontend/src/api/client.ts:61` (`refreshSession`).

**Evidence.** `const data = (await resp.json()) as {access_token}` runs on any 2xx without try/catch, and the top-level `fetch` can reject (network/CORS). Both throw out of `refreshSession` and thus out of `request()`, skipping the `clearAccessToken()` / `onUnauthorized()` path.

**Failure scenario.** If `/auth/refresh` returns 200 with an empty/non-JSON body, or the refresh fetch rejects (offline), the error propagates as an unhandled rejection instead of clearing the session and redirecting to login.

**Suggested fix.** Wrap the refresh fetch+json in try/catch, returning `false` on any parse/network failure so callers fall through to the clear-session path.

**Verification.** Confirmed 3/3 adversarial verifiers. No try/catch around `fetch` or `resp.json()`; a network reject or non-JSON 200 throws past the clear-session path. Minor resilience gap, low.

<a id="fro-17"></a>
### FRO-17 — Frontend inbox client drops backend `limit` and reuses Gmail type for Outlook/Yahoo
⚪ **LOW** · 🔁 consistency · Status: ✅ done · Confidence: medium (3/5 verifiers) · Effort: S · WS41

**Locations:** `frontend/src/api/inbox.ts:17` (`listReplyDrafts`).

**Evidence.** Backend `GET /inbox/reply-drafts` accepts a `limit` (`inbox.py:272`, up to 100) but `inbox.ts:17` never sends it. `outlookAuthorize`/`yahooAuthorize` (`:40–42`) are typed `GmailAuthorizeResult` even though the backend defines distinct `Outlook`/`YahooAuthorizeResponse` (`mailbox.py:50–55`) — identical today, latent drift.

**Failure scenario.** If a future Outlook/Yahoo authorize response diverges from Gmail's shape, the shared frontend type silently mis-types it; reply-drafts pagination is unreachable from the client.

**Suggested fix.** Expose `limit` in `listReplyDrafts` and give Outlook/Yahoo authorize their own frontend types mirroring the backend schemas.

**Verification.** Confirmed 3/3 adversarial verifiers. Real latent drift, low.

<a id="fro-18"></a>
### FRO-18 — Verify/Onboarding guards omit loading and !user checks, relying implicitly on nesting
⚪ **LOW** · 🔁 consistency · Status: ✅ done · Confidence: high (3/5 verifiers) · Effort: XS · WS41

**Locations:** `frontend/src/auth/EmailVerificationGuard.tsx:9` (`EmailVerificationGuard`); plus `frontend/src/auth/OnboardingGuard.tsx:9`.

**Evidence.** Both guards only branch on `user && !user.x`; they never handle `loading` or `!user` like `ProtectedRoute`/`AdminRoute` do. They are safe only because `App.tsx` nests them strictly inside `<ProtectedRoute>`. The sibling guards each independently check `loading` and `!user`.

**Failure scenario.** If either guard is ever mounted outside `ProtectedRoute` (refactor/reuse), a null/still-loading user passes through, rendering a protected `Outlet` to an unauthenticated visitor before redirect.

**Suggested fix.** Add explicit `loading`/`!user` handling to both guards (mirror `ProtectedRoute`), or document the hard nesting invariant, so guards are self-contained defense-in-depth.

**Verification.** Confirmed 3/3 adversarial verifiers. Currently safe defense-in-depth/consistency, low.

<a id="fro-19"></a>
### FRO-19 — Apply dialog init-focuses Close and lacks aria-describedby / live status
⚪ **LOW** · 🐞 bug · Status: ✅ done · Confidence: medium (3/5 verifiers) · Effort: S · WS41

**Locations:** `frontend/src/components/ApplyJobDialog.tsx:159` (`ApplyJobDialog`).

**Evidence.** The dialog has `role=dialog`/`aria-modal`/`aria-labelledby` but no `aria-describedby`; `useFocusTrap` sends initial focus to the first focusable element (the header "Close" button, `:169`) rather than the dialog or first field, and success/error state changes rely on non-live Banners (see FRO-29).

**Failure scenario.** On open, a screen-reader user hears only "Close button" with no dialog description; after submit, the queued→success/failure transition (async poll) is not announced.

**Suggested fix.** Add `aria-describedby` pointing at the intro paragraph, move initial focus to the dialog container or first field, and make status Banners live regions.

**Verification.** Confirmed 3/3 adversarial verifiers. `describedby`/focus and non-live banners are real a11y gaps, low.

<a id="fro-21"></a>
### FRO-21 — JsonEditor parse-error message is not an ARIA live region
⚪ **LOW** · 🐞 bug · Status: ✅ done · Confidence: medium (3/5 verifiers) · Effort: XS · WS41

**Locations:** `frontend/src/components/JsonEditor.tsx:49` (`JsonEditor`).

**Evidence.** On invalid JSON it renders `<span className="field-hint error-text">Invalid JSON: {error}</span>` with no `role`/`aria-live`, and the textarea sets only `className "invalid"` (no `aria-invalid` / `aria-describedby`).

**Failure scenario.** A screen-reader user editing a source/credential/search JSON config types invalid JSON; the inline validity error is neither announced nor associated with the textarea, so they get no error feedback.

**Suggested fix.** Add `aria-live="polite"` / `role="alert"` to the error span, set `aria-invalid` on the textarea, and link it via `aria-describedby`.

**Verification.** Confirmed 3/3 adversarial verifiers. Validity error unannounced, low.

<a id="fro-22"></a>
### FRO-22 — App shell has no skip-to-content link before the sidebar navigation
⚪ **LOW** · 🐞 bug · Status: ✅ done · Confidence: medium (3/5 verifiers) · Effort: XS · WS41

**Locations:** `frontend/src/components/Layout.tsx:96` (`Layout`).

**Evidence.** `<main className="content">` exists but no skip link precedes the sidebar nav; keyboard users must tab through the full `DESKTOP_NAV` (9–10 links) on every page before reaching content. A grep for "skip" in `src` returned no skip-navigation link.

**Failure scenario.** A keyboard-only user must tab past the entire sidebar navigation on each route to reach page content — a bypass-blocks failure.

**Suggested fix.** Add a visually-hidden "Skip to main content" anchor targeting the `<main>` region at the top of `Layout`.

**Verification.** Confirmed 3/3 adversarial verifiers. Bypass-blocks gap, low.

**Resolution.** Fixed in [PR](https://github.com/davidcristian/HeadStart/pull/239): `Layout` renders a `.skip-to-content` link as the first focusable control; on focus it becomes visible and targets `#main-content` (`<main tabIndex={-1}>`).

<a id="fro-33"></a>
### FRO-33 — CSS uses undefined vars --surface/--accent/--bg-muted with no fallback
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: high (3/5 verifiers) · Effort: XS · WS41

**Locations:** `frontend/src/index.css:1523` (`.cookie-consent`); plus `:764`, `:1553`, `:1834`, `:1979`, `:1989`, `:2009`, `:2029`, `:2063`.

**Evidence.** `:root` (lines 1–26) has no `--surface`/`--accent`/`--bg-muted`; a grep for their definitions returns none. Usages like `background: var(--surface)` (1523) and `color-mix(... var(--accent) ...)` (1989) have no fallback, so they compute to invalid/transparent.

**Failure scenario.** The cookie-consent banner (1523) renders transparent; portal cards/tabs (1979/1989/2063) and the reply-draft body (764) lose their surface color and accent borders — broken-looking UI on those views.

**Suggested fix.** Define `--surface`, `--accent`, `--bg-muted` in `:root` (or replace with the existing `--bg-elev`/`--brand` tokens), matching the intended palette.

**Verification.** Confirmed 3/3 adversarial verifiers. 11 sites use these vars but they are never defined; with no fallback they resolve invalid — a real low visual bug.

<a id="fro-30"></a>
### FRO-30 — useUpdateJob invalidates only ["jobs"], leaving the applications pipeline stale
⚪ **LOW** · 🐞 bug · Status: ✅ done · Confidence: high (3/5 verifiers) · Effort: XS · WS41

**Locations:** `frontend/src/hooks/jobMutations.ts:13` (`useUpdateJob`).

**Evidence.** `onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] })`. Marking a job applied/archived from `JobsPage` changes the pipeline stage (`applications.py:37–51` derives stage from `job.status`), but `["applications"]` is never invalidated.

**Failure scenario.** A user archives or marks-applied a job on `/app/jobs`, then opens `/app/applications`; the pipeline shows the stale stage until the 10s `staleTime` lapses or a manual refetch.

**Suggested fix.** In `useUpdateJob.onSuccess` also invalidate the `["applications"]` prefix key (as the sibling apply/draft mutations already do).

**Verification.** Confirmed 3/3 adversarial verifiers. Applications cache goes stale after a status change until `staleTime` lapses — minor UX staleness, low.

<a id="fro-31"></a>
### FRO-31 — useApplyToJob invalidates ["jobs"] only on sync submitted, not the async queued path
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: medium (3/5 verifiers) · Effort: S · WS41

**Locations:** `frontend/src/hooks/jobMutations.ts:46` (`useApplyToJob`).

**Evidence.** `onSuccess` only invalidates `["jobs"]` when `result.status === "submitted"`. The common path returns `"queued"` (`apply.py:55/78`), so the hook never refetches jobs; it relies solely on `ApplyJobDialog.tsx:139` invalidating `["jobs"]` after `pollApplicationLog` resolves.

**Failure scenario.** Any future caller of `useApplyToJob` not replicating `ApplyJobDialog`'s post-poll invalidation leaves the Jobs feed showing the job as un-applied after a successful live apply.

**Suggested fix.** Document the polling contract on the hook, or invalidate `["jobs"]` on the queued path too so the hook is self-sufficient.

**Verification.** Confirmed 3/3 adversarial verifiers. Latent low-severity contract gap; the hook is not self-sufficient.

<a id="fro-32"></a>
### FRO-32 — useFocusTrap re-runs on onClose identity change, stealing focus and breaking restore
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: high (3/5 verifiers) · Effort: S · WS41

**Locations:** `frontend/src/hooks/useFocusTrap.ts:68` (`useFocusTrap`); plus `frontend/src/components/ApplyJobDialog.tsx:54`, `frontend/src/pages/JobsPage.tsx:193`.

**Evidence.** The effect deps are `[active, containerRef, onClose]`; on cleanup it calls `previouslyFocused?.focus()` and on re-run it recaptures `document.activeElement` then `focusable()[0]?.focus()`. `ApplyJobDialog` receives `onClose={() => setApplyJob(null)}` (new identity each render).

**Failure scenario.** While the Apply dialog is open, any `JobsPage` re-render (jobs refetch/poll, `refetchOnWindowFocus` after 10s, mutation invalidations) re-runs the trap: focus jumps back to the dialog's Close button mid-typing and the restore target is overwritten, so focus is not returned to the trigger on close.

**Suggested fix.** Drop `onClose` from the deps (use a ref for the latest callback) so focus is captured/moved once per open; or memoize `onClose` at the call sites.

**Verification.** Confirmed 3/3 adversarial verifiers. Re-render sources exist that re-run the trap to steal focus and overwrite the restore target.

<a id="fro-34"></a>
### FRO-34 — Date/time rendered in the browser's implicit locale and timezone with no fixed formatting
⚪ **LOW** · 🔁 consistency · Status: ☐ open · Confidence: high (5/5 verifiers) · Effort: S · WS41

**Locations:** `frontend/src/lib/format.ts:16` (`formatDateTime`); plus `frontend/src/components/AdminDataRequestsCard.tsx:36`, `frontend/src/components/profile/ApplicationHistoryTable.tsx:30`, `frontend/src/components/ApplicationPipelineList.tsx:176`, `frontend/src/components/JobList.tsx:174`, `frontend/src/pages/AdminPage.tsx:58`, `frontend/src/pages/AdminPage.tsx:143`, `frontend/src/components/profile/ProfileDetailsForm.tsx:229`.

**Evidence.** `new Date(iso).toLocaleString()` and `.toLocaleDateString()` are called with no locale/options/timeZone across ~8 sites, so the output format (M/D/Y vs D.M.Y) and timezone depend entirely on the viewer's environment — nondeterministic and untested for a DE audience.

**Failure scenario.** A German user sees US-format timestamps (or a Chrome with en-US locale renders M/D/Y); with no timezone shown, application/run times are ambiguous across DST/timezones.

**Suggested fix.** Centralize formatting with an explicit locale + timeZone (e.g. `Intl.DateTimeFormat`) and route all timestamp rendering through one helper.

**Verification.** Confirmed 5/5 adversarial verifiers. All sites use `toLocale*()` with no locale/timeZone — environment-dependent, low.

<a id="fro-35"></a>
### FRO-35 — Billing and pricing are USD-only while the product legally targets the German market
⚪ **LOW** · 🔁 consistency · Status: ☐ open · Confidence: high (2/3 verifiers) · Effort: M · WS41

**Locations:** `frontend/src/lib/pricing.ts:176` (`formatUsd`); plus `frontend/src/pages/PricingPage.tsx:141`, `backend/app/services/promo_codes.py:262`, `frontend/src/pages/ImpressumPage.tsx:8`.

**Evidence.** `PLANS` prices render via `formatUsd` (`$2.99`, `/ month`) and Stripe promo coupons hardcode `"currency": "usd"`, yet `ImpressumPage.tsx` ships a German § 5 TMG / § 18 MStV legal notice — the product is provisioned for a German/EU consumer market where prices are legally expected in EUR incl. VAT.

**Failure scenario.** A German consumer sees prices in USD without VAT disclosure and is charged in USD; this conflicts with the DE Impressum and EU price-indication expectations (VAT-inclusive, local currency).

**Suggested fix.** Make display currency and Stripe coupon currency configurable (EUR for the DE instance), and show VAT-inclusive pricing on the pricing page.

**Verification.** Confirmed 2/3 adversarial verifiers (1 refuted). `formatUsd` and `currency='usd'` are hardcoded, but `ImpressumPage` is explicitly a placeholder "before publicly used in Germany"; DE targeting and the EUR/VAT duty are speculative and operator-config dependent, so low.

<a id="fro-36"></a>
### FRO-36 — Admin scrape-errors and Users cards render blank while loading
⚪ **LOW** · 🔁 consistency · Status: ☐ open · Confidence: high (3/5 verifiers) · Effort: XS · WS41

**Locations:** `frontend/src/pages/AdminPage.tsx:124` (`AdminPage`); plus `frontend/src/pages/AdminPage.tsx:163`.

**Evidence.** `{s && s.recent_errors.length === 0 ? <EmptyState/> : (s && <table/>)}` and the Users card both short-circuit to `false` while data is `undefined`, rendering an empty body. The "System overview" card shows "Loading stats...", so it is inconsistent.

**Failure scenario.** On a slow admin fetch these two cards appear blank (no spinner/placeholder) until data arrives, unlike the overview card; minor UX inconsistency, no data impact.

**Suggested fix.** Render a loading/EmptyState when `stats.isPending` / `users.isPending`, mirroring the existing "Loading stats..." placeholder.

**Verification.** Confirmed 3/3 adversarial verifiers. Genuine UX inconsistency, low.

<a id="fro-37"></a>
### FRO-37 — German legal pages display effective dates in US English long format
⚪ **LOW** · 🔁 consistency · Status: ☐ open · Confidence: high (5/5 verifiers) · Effort: XS · WS41

**Locations:** `frontend/src/pages/ImpressumPage.tsx:6` (`EFFECTIVE_DATE`); plus `frontend/src/components/LegalPageLayout.tsx:26`, `frontend/src/pages/PrivacyPolicyPage.tsx:6`, `frontend/src/pages/TermsOfUsePage.tsx:5`, `frontend/src/pages/SubprocessorsPage.tsx:6`.

**Evidence.** The `ImpressumPage` body is entirely German (§ 5 TMG) but `EFFECTIVE_DATE = "June 29, 2026"` and `LegalPageLayout` renders the hardcoded English label `Effective {date}` — a German legal notice should use a German date ("29. Juni 2026") and a German label.

**Failure scenario.** German users reading the Impressum/Datenschutz see an English "Effective June 29, 2026" header — an L10n inconsistency on a page that must read as German legal text.

**Suggested fix.** Use German-formatted dates and a localized "Stand/Gültig ab" label on the German legal pages (or drive from locale).

**Verification.** Confirmed 5/5 adversarial verifiers. Confirmed i18n inconsistency, low.

<a id="fro-38"></a>
### FRO-38 — Jobs filter <select>s wrapped in <Field label=""> have an empty accessible name
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: high (3/5 verifiers) · Effort: XS · WS41

**Locations:** `frontend/src/pages/JobsPage.tsx:148` (Discovered jobs filters); plus `frontend/src/pages/JobsPage.tsx:157`.

**Evidence.** Two `<Field label="">` wrap the status and search-scope selects (`:149`, `:158`). `Field` renders `<span className="field-label">{label}</span>` = empty, so the wrapping `<label>`'s text is blank; the selects have no `aria-label` and no visible name.

**Failure scenario.** A screen-reader user on the Jobs page tabs to two unlabeled comboboxes ("combobox" announced with no name) and cannot tell which filters by status and which by search.

**Suggested fix.** Give each select a real label or `aria-label` (e.g. "Filter by status", "Filter by search") instead of `label=""`.

**Verification.** Confirmed 3/3 adversarial verifiers. No accessible name — confirmed WCAG 4.1.2, low.

<a id="fro-39"></a>
### FRO-39 — Onboarding progress steps convey current step only via CSS class, not aria-current
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: high (3/5 verifiers) · Effort: XS · WS41

**Locations:** `frontend/src/pages/OnboardingPage.tsx:28` (OnboardingPage steps).

**Evidence.** The `<ol aria-label="Setup progress">` marks the active step with `className` 'current'/'done' only; no `aria-current="step"` and no text like "current step". Visual-only state.

**Failure scenario.** A screen-reader user in the onboarding wizard cannot perceive which numbered step is active or completed; progress is conveyed by color/weight alone.

**Suggested fix.** Add `aria-current="step"` to the active `<li>` (and/or visually-hidden "completed"/"current" text).

**Verification.** Confirmed 3/3 adversarial verifiers. State conveyed visually only — confirmed low a11y.

<a id="fro-41"></a>
### FRO-41 — Category tablists have role=tab but no linked tabpanel or roving tabindex
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: medium (5/5 verifiers) · Effort: S · WS41

**Locations:** `frontend/src/pages/sources/PortalCatalog.tsx:71` (`portal-category-tabs`); plus `frontend/src/pages/portals/PortalsSearchCard.tsx:48`.

**Evidence.** `role=tablist` with `role=tab` buttons and `aria-selected`, but no `aria-controls`, no element with `role=tabpanel`, and no arrow-key roving tabindex (all tabs remain in tab order). The filtered grid below is a plain `<ul>`, not a tabpanel.

**Failure scenario.** A screen-reader user hears "tab, selected" with no associated panel; keyboard users get no ARIA-authoring-practices arrow-key navigation between category tabs.

**Suggested fix.** Either link tabs to a `role=tabpanel` via `aria-controls` with roving tabindex, or drop the tab roles and expose the category filter as a labelled button group.

**Verification.** Confirmed 5/5 adversarial verifiers. Real ARIA gap, low.

<a id="fro-29"></a>
### FRO-29 — Shared Banner has no ARIA live-region role; async errors/success never announced
⚪ **LOW** · 🐞 bug · Status: ✅ done · Confidence: high (3/5 verifiers) · Effort: S · WS41

**Locations:** `frontend/src/components/ui.tsx:59` (`Banner`); plus `frontend/src/components/ApplyJobDialog.tsx:262`, `:197`, `frontend/src/pages/LoginPage.tsx:44`, `frontend/src/pages/OnboardingPage.tsx:44`, `frontend/src/pages/SettingsPage.tsx:141`, `frontend/src/pages/sources/PortalCatalog.tsx:105`.

**Evidence.** `Banner` renders `<div className="banner banner-{kind}">` with no `role`/`aria-live`. It is the app-wide sink for async errors and success (47 call sites), e.g. `ApplyJobDialog` apply error (`:262`) and "Application submitted" success (`:197`) rendered conditionally after an action.

**Failure scenario.** A screen-reader user submits an auto-apply, login, or export; the resulting error/success Banner appears silently. They get no feedback and cannot tell the action failed or succeeded.

**Suggested fix.** Give `Banner` `role="alert"`/`aria-live="assertive"` for `kind=error` and `role="status"`/`aria-live="polite"` for info/success (or accept a `role` prop).

**Verification.** Confirmed 3/3 adversarial verifiers. Genuine WCAG 4.1.3 gap across 47 conditional call sites, low.

<a id="fro-24"></a>
### FRO-24 — Resume/template uploads have no client-side size/type gate despite stated limits
⚪ **LOW** · 🐞 bug · Status: ✅ done · Confidence: high (3/5 verifiers) · Effort: S · WS41

**Locations:** `frontend/src/components/profile/ProfileDetailsForm.tsx:146` (`ProfileDetailsForm`).

**Evidence.** File inputs forward `e.target.files?.[0]` straight to the upload mutation with no size check; the hint says "up to 2 MB" but the whole file uploads before the server (`profiles.py:230`) rejects it. `accept=` is advisory only.

**Failure scenario.** A user selects a 50 MB PDF; the full body uploads over a slow link only to get a late "exceeds 2 MB" error — wasted bandwidth and confusing UX with no pre-flight feedback.

**Suggested fix.** Pre-validate `File.size` against the documented limits (and extension) before `mutateAsync`, surfacing an inline error immediately.

**Fix.** `ProfilePage` runs `validateResumeUpload` / `validateResumeTemplateUpload` (defaults matching `PROFILE_RESUME_*_MAX_BYTES`) before mutate; wrong extension or oversize surfaces via the existing error Banner without calling the API. Template hint documents 512 KB / 2 MB caps. — [PR](https://github.com/davidcristian/HeadStart/pull/240)

**Verification.** Confirmed 3/3 adversarial verifiers. A low UX/pre-flight gap only; the server enforces the real limit.

<a id="fro-25"></a>
### FRO-25 — SkillsLanguagesForm redefines updateRow instead of importing profileFormUtils
⚪ **LOW** · 🔁 consistency · Status: ✅ done · Confidence: certain (3/5 verifiers) · Effort: XS · WS41 · [PR](https://github.com/davidcristian/HeadStart/pull/241)

**Locations:** `frontend/src/components/profile/SkillsLanguagesForm.tsx:19` (`updateRow`).

**Evidence.** Lines 19–21 define a local `function updateRow<T>(...)` byte-identical to `profileFormUtils.updateRow` (lines 10–12), which the siblings `EducationSection`/`WorkExperienceSection` import. Divergent copies drift and are covered by two separate tests.

**Failure scenario.** A future fix to the shared `updateRow` (e.g. immutability/edge handling) silently misses this form; maintainers must know two copies exist.

**Suggested fix.** Delete the local `updateRow` and import `{ updateRow }` from `./profileFormUtils` like the sibling sections.

**Verification.** Confirmed 3/3 adversarial verifiers. A real DRY/duplication drift risk.

<a id="fro-26"></a>
### FRO-26 — Checkbox rows nest a <label> inside the Field <label> (invalid HTML, ambiguous a11y)
⚪ **LOW** · 🐞 bug · Status: ✅ done · Confidence: high (3/5 verifiers) · Effort: S · WS41

**Locations:** `frontend/src/components/profile/WorkExperienceSection.tsx:120` (`WorkExperienceSection`); plus `frontend/src/components/profile/SkillsLanguagesForm.tsx:109`, `frontend/src/components/ui.tsx:46`.

**Evidence.** `<Field label="Current role">` renders `<label class="field">` (`ui.tsx:46`) and inside it a second `<label className="checkbox-row">` wraps the checkbox. Nested `<label>` is invalid HTML; the outer field label also captures the checkbox. Same pattern in `SkillsLanguagesForm` "Native language".

**Failure scenario.** Screen-reader/AT users get an ambiguous or doubled label for the `is_current`/`is_native` checkbox; some browsers associate the outer field label's click with the checkbox unexpectedly.

**Suggested fix.** Render the checkbox row as a `<div>` (like `AdminPromoCodesCard`) or drop the wrapping `<Field>`; keep a single `<label>` per checkbox.

**Verification.** Confirmed 3/3 adversarial verifiers. Nested labels are invalid HTML with ambiguous a11y and no upstream guard, low.

<a id="fro-27"></a>
### FRO-27 — parseOptionalInt accepts negative/decimal years and months (min/max not enforced)
⚪ **LOW** · 🐞 bug · Status: ✅ done · Confidence: medium (2/3 verifiers) · Effort: S · WS41

**Locations:** `frontend/src/components/profile/profileFormUtils.ts:3` (`parseOptionalInt`); plus `frontend/src/components/profile/WorkExperienceSection.tsx:95`, `frontend/src/components/profile/EducationSection.tsx:81`.

**Evidence.** `Number(trimmed)` is returned whenever finite, with no integer/range check. Inputs set `min`/`max` (1900–2100, 1–12) but those HTML attributes are non-enforcing hints, so `start_year=3.5` or `end_month=-2` flow into the profile payload unmodified.

**Failure scenario.** A user types a decimal/negative year or month; the malformed value is sent to the profile API and later to Workday auto-apply payload builders, risking a rejected or mis-dated application.

**Suggested fix.** Round/floor to an integer and clamp to the field's min/max before storing, or rely on a validated schema.

**Verification.** Confirmed 2/3 adversarial verifiers (1 refuted). Decimals/negatives pass through; HTML min/max are non-enforcing hints.

<a id="fro-28"></a>
### FRO-28 — SMTP password field lacks the 'write-only' hint its IMAP-password sibling carries
⚪ **LOW** · 🔁 consistency · Status: ✅ done · Confidence: certain (3/5 verifiers) · Effort: XS · WS41

**Locations:** `frontend/src/components/settings/SettingsInboxImapForm.tsx:54` (`SettingsInboxImapForm`).

**Evidence.** The IMAP password Field has the hint "Write-only; not shown after save." (line 40) but the SMTP password Field (line 54) has none, even though the backend never returns either secret on read (`mailbox.py` docstring). Both blank on reload identically.

**Failure scenario.** A user re-opens Settings, sees the SMTP password blank with no explanation (unlike IMAP), assumes the credential was lost, and re-enters it — inconsistent credential UX.

**Suggested fix.** Add the same "Write-only; not shown after save." hint to the SMTP password Field.

**Verification.** Confirmed 3/3 adversarial verifiers. A genuine consistency/UX inconsistency, low.

<a id="fro-40"></a>
### FRO-40 — Retention section omits post-deletion audit-email retention and inbox data
⚪ **LOW** · 📝 doc · Status: ✅ done · Confidence: high (3/5 verifiers) · Effort: S · WS18

**Locations:** `frontend/src/pages/PrivacyPolicyPage.tsx:120` (`PrivacyPolicyPage`).

**Evidence.** Retention says deleting resources removes rows and account deletion is permanent, but `data_request_log` keeps `user_email` after deletion (`nullable=False`, `user_id SET NULL`) and the app processes recruiter email content (`inbox_reply_draft.body_text`) — neither retention behavior is disclosed.

**Failure scenario.** A data subject reads that deletion is complete/permanent, but their email persists in the audit log and recruiter-email PII was processed; the stated retention model is inaccurate.

**Suggested fix.** Document audit-log retention (email kept for compliance) and inbox/recruiter-email processing + retention in the Retention section.

**Verification.** Confirmed 3/3 adversarial verifiers. Doc-drift is real, low.

<a id="fro-42"></a>
### FRO-42 — tsconfig omits noUncheckedIndexedAccess for a hand-typed API client
⚪ **LOW** · ♻️ refactor · Status: ☐ open · Confidence: medium (3/5 verifiers) · Effort: M · WS41

**Locations:** `frontend/tsconfig.json:14` (`compilerOptions`).

**Evidence.** `compilerOptions` has `strict` + `noUnusedLocals`/`Parameters` + `noFallthroughCasesInSwitch` but not `noUncheckedIndexedAccess` or `exactOptionalPropertyTypes`. The codebase hand-mirrors backend schemas with many optional fields and array/record indexing.

**Failure scenario.** Array/record index access (e.g. `features[key]`, `list[i]`) is typed as non-undefined; a missing key returns `undefined` at runtime with no compile error, masking exactly the optional/drift mismatch this hand-typed layer is prone to.

**Suggested fix.** Enable `noUncheckedIndexedAccess` (and consider `exactOptionalPropertyTypes`) and fix the resulting spots; this strengthens the sync-by-convention type layer.

**Verification.** Confirmed 3/3 adversarial verifiers. Genuine hardening for the hand-typed API layer, low.
