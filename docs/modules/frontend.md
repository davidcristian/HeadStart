# Module: Frontend

**Path:** `frontend/`

React + TypeScript (Vite). Built to a static bundle
and served by nginx in a container (which also reverse-proxies `/api` to the backend
in production).

## Structure

| Path                | Contents                                            |
| ------------------- | --------------------------------------------------- |
| `src/api/`          | Typed API client (one function per endpoint)        |
| `src/auth/`         | `AuthContext`, `ProtectedRoute` (session state)     |
| `src/types/`        | TS types mirroring backend schemas                  |
| `src/hooks/`        | React Query data hooks (`queries.ts`/`mutations.ts`) + UI state hooks |
| `src/components/`   | Reusable presentational components (`Brand`, `Layout`, …) |
| `src/pages/`        | Route-level screens                                 |

## Routing: public site vs. authenticated app

The frontend serves two surfaces from one bundle (see
[App.tsx](../../frontend/src/App.tsx)):

- **Public** (no auth, no app shell): `/` landing page, `/pricing`, `/privacy`, `/terms`, `/impressum`, plus the auth screens
  `/login`, `/register`, `/forgot-password`, `/reset-password`.
- **Cookie consent:** a fixed bottom banner (`CookieConsentProvider` in `main.tsx`)
  asks for **Essential only** vs **Accept all** on first visit. The choice is stored in
  `localStorage` (`headstart.cookieConsent`), not a cookie. Visitors can reopen the banner
  from **Cookie settings** in the public footer or **Settings → Privacy & cookies** in the
  app. Components gate optional third-party content (e.g. ad iframes, see **Free-tier ads**
  below) on the reactive `useCookieConsent()` context; `acceptsOptionalCookies()` from
  `src/lib/cookieConsent.ts` is the non-reactive equivalent for one-off checks. The built-in
  upgrade promotion does not use tracking cookies.
- **Authenticated product** under **`/app/*`**, gated by `ProtectedRoute` and
  wrapped in the `Layout` shell (`/app/searches`, `/app/jobs`, …, `/app/admin`).
  `/app` redirects to `/app/searches`. Unverified accounts are redirected to
  `/verify-email` by `EmailVerificationGuard`. New accounts without
  `onboarding_completed_at` are redirected to **`/app/onboarding`** (guided
  setup wizard) before they can reach the main shell.

Register returns a uniform success ack and sends new accounts to `/verify-email`
without auto-login (so duplicate emails cannot be inferred from a follow-up
login failure). Login sends users to `/app`, where the verification and
onboarding guards redirect as needed. Already-authenticated
visitors to auth screens bounce to `/app`. Legacy top-level paths (`/jobs`,
`/searches`, …) 301-style redirect to their `/app/*` equivalent so old
bookmarks and the installed PWA (`start_url: /app/jobs`) keep working. Any
other unknown path redirects to the landing page.

## Pages

| Page        | Purpose                                                          |
| ----------- | ---------------------------------------------------------------- |
| Landing     | Public marketing page at `/`: hero with app screenshots, tabbed product demo, integrations strip, how-it-works, features, FAQ, CTA to register/sign in |
| Pricing     | Public pricing page at `/pricing`: Free / Starter / Plus / Pro tiers (mirrors backend `plans.py`), feature comparison table, monthly vs annual toggle; Free and paid CTAs link to register; signed-in users can self-serve checkout for Starter, Plus, or Pro when billing is configured |
| Privacy     | Public privacy policy at `/privacy`; discloses AI purposes (summaries, cover letters, resume curation, email classification, reply drafting) and the profile / recruiter-email categories each may send to configured LLM providers; discloses auto-apply transmission of application-profile PII to career sites, lawful basis (consent for opt-in third-party sends), and per-attempt consent stamps on application logs; Retention covers inbox/recruiter-email data (kept while the mailbox is connected, removed on account deletion) and the post-deletion `data_request_log` compliance row (HMAC email pseudonym only — no plaintext email/IP/UA) |
| Subprocessors | Public Art.28 list at `/subprocessors`; includes AWS, Stripe, OpenAI, Google Gemini, Anthropic, Gmail / Outlook / Yahoo mailbox OAuth, and SMTP — operators may disable unused providers |
| Terms       | Public terms of use at `/terms` |
| Impressum   | Public German legal notice at `/impressum`; operators customize content per [launch-checklist.md §4](../launch-checklist.md#4-legal--trust-pages) |
| Login/Register    | Email + password sign-in / sign-up                               |
| Verify email      | Confirm address after signup at `/verify-email` (link or resend)   |
| Onboarding  | First-run wizard at `/app/onboarding`: source → notify → search → run |
| Sources     | List/create/edit sources (name, adapter, base URL, config); browse curated company portals; test scrape |
| Companies   | Pro+ cross-portal search at `/app/portals`: keyword search across curated FAANG/unicorn/AI boards (selection capped at 30 to match the API `portal_ids` max), results preview, one-click alert setup |
| Searches    | Create a search: pick source + target, query URL + structured filters (keywords, location, workplace, salary) + |
|             | interval; enable/disable; run now (queues Celery; UI polls `search_run`); view last |
|             | run, scrape errors, and recent delivery failures                 |
| Jobs        | Feed of seen jobs, filterable by search and status; mark seen/applied/archived; **Apply** on supported sources (preview + submit; generate cover letter / tailored resume via queued `document_generation` poll); salary when scraped; copy RSS feed URL |
| Applications | Pipeline view at `/app/applications`: applied jobs with derived stage (`queued`, `awaiting_reply`, `apply_failed`, `closed`, `archived`), attempt timeline, and stage filter; see `GET /applications` |
| Profile     | Application profile for auto-apply (contact, resume, experience, education, skills); application history table |
| Targets     | Manage notification targets (e.g. ntfy server/topic); send test  |
| Credentials | Per-source encrypted cookies/headers for bot-walled sites        |
| Settings    | API base URL, billing (tier-aware upgrade checkout + portal), account export/delete, cookie prefs, ntfy help |
| Admin       | User management (assign free/starter/plus/pro), promo codes, GDPR audit, global scrape/delivery stats (admin only) |

## Auth flow

- Login returns the access token (kept **in memory** in `src/lib/settings.ts`);
  the refresh token is an httpOnly cookie set by the backend. See
  [auth.md](auth.md) and [adr/0007-httponly-refresh-cookie.md](../adr/0007-httponly-refresh-cookie.md).
- `/forgot-password` and `/reset-password?token=...` for email-based password reset.
- `/verify-email` and `/verify-email?token=...` for email verification after signup.
  Unverified users can sign in but product routes return **403** until verified.
- `src/api/client.ts` sends `credentials: "include"`, attaches the in-memory
  access token, and on a 401 calls `refreshSession()` (cookie-based) once before
  clearing the session.
- `AuthProvider` (in `main.tsx`) resolves the current user; `ProtectedRoute`
  gates all app routes and redirects to `/login`. See [auth.md](auth.md).

## Data fetching (React Query)

Server state is managed by **TanStack Query** (`@tanstack/react-query`). The
`QueryClient` is provided once in `src/main.tsx`.

- **Reads:** `src/hooks/queries.ts` exposes one `useXxx()` hook per resource
  (`useSources`, `useJobs`, `useAdminStats`, …) and owns the `queryKeys`
  registry. Components read `data` / `isPending` / `isError` from these.
- **Writes:** `src/hooks/mutations.ts` exposes `useCreateXxx` / `useUpdateXxx` /
  `useDeleteXxx` hooks. Each calls the typed API client and invalidates the
  query keys it affects, so lists re-fetch authoritative data instead of pages
  hand-mutating local state. Components call `mutation.mutateAsync(...)`.
- The hooks still call `src/api/` under the hood — React Query only adds
  caching, background revalidation, and dedupe on top of the typed client.
- **Session isolation:** `AuthProvider` calls `queryClient.clear()` on
  successful `login`, on `logout`, and when the API client's unauthorized
  handler fires (hard 401 after refresh failure). Query keys are not
  user-scoped, so clearing prevents a shared-browser logout→login from
  briefly serving the previous account's cached PII.

## Conventions

- Strict TypeScript; prettier + eslint. `just lint --frontend` runs both
  `eslint` and `prettier --check` (CI uses the same recipe).
- All network calls go through `src/api/` (wrapped by the React Query hooks in
  `src/hooks/`) using `VITE_API_BASE_URL`. Components do not call `api.*`
  directly.
- The API client attaches the bearer token to every request automatically; pages
  never handle tokens directly.
- **Scraped / untrusted URLs:** never put a job or portal URL into `href`
  without `safeHref()` from `src/lib/safeHref.ts`. It allows only `http:` /
  `https:` and returns `null` for `javascript:`, `data:`, relative paths, and
  other schemes — callers render plain text instead of an anchor. Used by
  `JobList`, `ApplicationPipelineList`, `SearchHealth`,
  `ApplicationHistoryTable`, and `PortalsResultsCard`.

## Tests

- Vitest + React Testing Library + jsdom (`npm run test` / `just test --frontend`).
- Page smoke tests live next to each page under `src/pages/*.test.tsx`; they mock
  `src/api/` via `src/test/mockApi.ts` and shared fixtures in `src/test/fixtures.ts`.
  Pages are rendered with `renderWithClient` (`src/test/renderWithClient.tsx`),
  which wraps them in a fresh React Query client per test.
- Covered pages: Sources, Searches, Targets, Jobs, Applications, Admin (render, empty state, list data,
  and primary actions like create/delete/test/run).
- `FreeTierAd.test.tsx` covers free vs paid gating and optional-cookie gating for partner slots.

## Free-tier ads

Free-plan users (`plan.show_ads` from `GET /api/v1/meta`) see a non-intrusive **Sponsored**
card in the app shell (`FreeTierAd` in `Layout.tsx`): sidebar on desktop, compact strip above
the mobile bottom nav. Paid plans and admin accounts see nothing.

- **House promotion** — built-in “Go ad-free with Pro” CTA linking to `/pricing` (no
  third-party tracking).
- **Partner slot (optional)** — operators set `ADS_EXTERNAL_SLOT_URL` (HTTPS iframe URL) in
  the backend env. The iframe loads only when the user has accepted optional cookies —
  `FreeTierAd` reads the choice from `CookieConsentContext` (not `localStorage` directly) so it
  reacts to consent changes without a reload. Otherwise a short link to
  **Settings → Privacy & cookies** is shown. The partner iframe uses
  `sandbox="allow-scripts allow-popups"` (no `allow-same-origin`) so a same-origin or
  open-redirect slot cannot lift its own sandbox and script the parent app (FRO-20).
- **Kill switch** — `ADS_ENABLED=false` hides all in-app ads (house + partner).

## Dev

- Standalone: `npm run dev` (Vite dev server on :5173, proxying to the API).
- In the stack: served by unprivileged nginx on container port **8080**
  (`nginxinc/nginx-unprivileged`; see `frontend/Dockerfile`,
  `frontend/nginx.conf`). Compose maps host `:8080` → container `:8080`; ECS
  / ALB target the same port. The HTML shell (`location /`), service worker
  assets (`sw.js`, `manifest.webmanifest`) are served with
  `Cache-Control: no-cache` so deploys revalidate the shell that references
  hashed `/assets/` (immutable, 1y). Without that, a cached `index.html` can
  point at asset hashes nginx no longer has.
- **Non-root runtime (FRO-08):** the SPA image does not use stock
  `nginx:*-alpine` (master as root on :80). The unprivileged image runs as the
  `nginx` user and binds only to 8080.
- **Security headers (production nginx):** the SPA `location /` block sets
  `Content-Security-Policy` (same-origin scripts; Google Fonts; HTTPS
  `connect-src` / partner-ad `frame-src`; `frame-ancestors 'none'`),
  `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: strict-origin-when-cross-origin`,
  `Strict-Transport-Security` (ALB terminates TLS; HSTS still applies on
  HTTPS responses), and a locked-down `Permissions-Policy`. Asset and
  service-worker locations repeat `nosniff` because nginx does not inherit
  `add_header` into locations that define their own.

### Marketing screenshots

The landing page hero and tabbed product demo use static PNGs in
`frontend/public/marketing/`. Regenerate them after meaningful UI changes:

1. Start the stack (`just dev`) and ensure the DB is seeded (`just seed`).
2. Install Playwright Chromium once: `pip install playwright && playwright install chromium` (in the backend venv).
3. Run `./scripts/capture_marketing_screenshots.py` (seeds demo jobs for the
   screenshot user, logs in via the UI, writes `searches.png`, `jobs.png`, and
   `notification.png`).

Commit the updated images when the app chrome changes.

## Toolchain & dependency security

Vite **6.4.3+** (with `overrides.esbuild: ^0.25.0`) keeps the locked esbuild
past [GHSA-67mh-4wv8-2f99](https://github.com/advisories/GHSA-67mh-4wv8-2f99)
(dev-server CORS SSRF in esbuild ≤0.24.2). Vitest / `@vitest/coverage-v8` track
**3.2.7+** so `npm audit --audit-level=high` stays clean. CI runs
`just audit-frontend` after `npm ci`; Dependabot watches `frontend/package-lock.json`
weekly (`.github/dependabot.yml`). Backend pip-audit is still tracked as OPS-19.

## Progressive Web App (mobile)

The frontend is installable as a PWA for a lightweight mobile jobs feed.

- **Manifest + icons** — `vite-plugin-pwa` generates `manifest.webmanifest` and
  registers a Workbox service worker on build. Static icons live in `public/`.
- **Install** — On mobile Chrome/Safari, use “Add to Home Screen”. The installed
  app opens on `/jobs` (`start_url` in the manifest).
- **Offline** — Cached shell (HTML/JS/CSS); API calls still require network.
- **Mobile layout** — Below 900px width the sidebar becomes a fixed bottom nav
  (Jobs, Searches, Sources, More). The Jobs page uses card rows instead of a
  table, hides the RSS card, and supports pull-to-refresh.
- **"More" sheet a11y** — The bottom-sheet dialog is `role="dialog"
  aria-modal="true"` and uses `useFocusTrap` (`src/hooks/useFocusTrap.ts`):
  opening moves focus into the sheet, Tab/Shift+Tab cycle within it, Escape
  closes it, and focus returns to the trigger on close.
