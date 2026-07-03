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
  app. Use `acceptsOptionalCookies()` from `src/lib/cookieConsent.ts` before loading optional
  third-party ad iframes (see **Free-tier ads** below). The built-in upgrade promotion does
  not use tracking cookies.
- **Authenticated product** under **`/app/*`**, gated by `ProtectedRoute` and
  wrapped in the `Layout` shell (`/app/searches`, `/app/jobs`, …, `/app/admin`).
  `/app` redirects to `/app/searches`. Unverified accounts are redirected to
  `/verify-email` by `EmailVerificationGuard`. New accounts without
  `onboarding_completed_at` are redirected to **`/app/onboarding`** (guided
  setup wizard) before they can reach the main shell.

Login/Register send new users to `/app/onboarding` on success (register) or
`/app` (login, which the onboarding guard redirects). Already-authenticated
visitors to auth screens bounce to `/app`. Legacy top-level paths (`/jobs`,
`/searches`, …) 301-style redirect to their `/app/*` equivalent so old
bookmarks and the installed PWA (`start_url: /app/jobs`) keep working. Any
other unknown path redirects to the landing page.

## Pages

| Page        | Purpose                                                          |
| ----------- | ---------------------------------------------------------------- |
| Landing     | Public marketing page at `/`: hero with app screenshots, tabbed product demo, integrations strip, how-it-works, features, FAQ, CTA to register/sign in |
| Pricing     | Public pricing page at `/pricing`: Free / Starter / Plus / Pro tiers (mirrors backend `plans.py`), feature comparison table, monthly vs annual toggle; Free and paid CTAs link to register; signed-in users can self-serve checkout for Starter, Plus, or Pro when billing is configured |
| Privacy     | Public privacy policy at `/privacy` |
| Terms       | Public terms of use at `/terms` |
| Impressum   | Public German legal notice at `/impressum` (placeholder operator details; replace before DE launch) |
| Login/Register    | Email + password sign-in / sign-up                               |
| Verify email      | Confirm address after signup at `/verify-email` (link or resend)   |
| Onboarding  | First-run wizard at `/app/onboarding`: source → notify → search → run |
| Sources     | List/create/edit sources (name, adapter, base URL, config); browse curated company portals; test scrape |
| Companies   | Pro+ cross-portal search at `/app/portals`: keyword search across curated FAANG/unicorn/AI boards, results preview, one-click alert setup |
| Searches    | Create a search: pick source + target, query URL + structured filters (keywords, location, workplace, salary) + |
|             | interval; enable/disable; run now (immediate results); view last |
|             | run, scrape errors, and recent delivery failures                 |
| Jobs        | Feed of seen jobs, filterable by search and status; mark seen/applied/archived; **Apply** on supported sources (preview + submit); salary when scraped; copy RSS feed URL |
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

## Conventions

- Strict TypeScript; prettier + eslint.
- All network calls go through `src/api/` (wrapped by the React Query hooks in
  `src/hooks/`) using `VITE_API_BASE_URL`. Components do not call `api.*`
  directly.
- The API client attaches the bearer token to every request automatically; pages
  never handle tokens directly.

## Tests

- Vitest + React Testing Library + jsdom (`npm run test` / `make test --frontend`).
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
  the backend env. The iframe loads only when the user has accepted optional cookies
  (`acceptsOptionalCookies()`). Otherwise a short link to **Settings → Privacy & cookies** is
  shown.
- **Kill switch** — `ADS_ENABLED=false` hides all in-app ads (house + partner).

## Dev

- Standalone: `npm run dev` (Vite dev server on :5173, proxying to the API).
- In the stack: served by nginx on :8080 (see `frontend/Dockerfile`,
  `frontend/nginx.conf`). Service worker assets (`sw.js`, `manifest.webmanifest`)
  are served with `Cache-Control: no-cache` so updates propagate.

### Marketing screenshots

The landing page hero and tabbed product demo use static PNGs in
`frontend/public/marketing/`. Regenerate them after meaningful UI changes:

1. Start the stack (`make dev`) and ensure the DB is seeded (`make seed`).
2. Install Playwright Chromium once: `pip install playwright && playwright install chromium` (in the backend venv).
3. Run `./scripts/capture_marketing_screenshots.py` (seeds demo jobs for the
   screenshot user, logs in via the UI, writes `searches.png`, `jobs.png`, and
   `notification.png`).

Commit the updated images when the app chrome changes.

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
