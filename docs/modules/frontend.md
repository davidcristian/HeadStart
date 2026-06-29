# Module: Frontend

**Path:** `frontend/`

React + TypeScript (Vite). Built to a static bundle and served by nginx in a
container (which also reverse-proxies `/api` to the backend in production).

## Structure

| Path                | Contents                                            |
| ------------------- | --------------------------------------------------- |
| `src/api/`          | Typed API client (one function per endpoint)        |
| `src/auth/`         | `AuthContext`, `ProtectedRoute` (session state)     |
| `src/types/`        | TS types mirroring backend schemas                  |
| `src/hooks/`        | React Query data hooks (`queries.ts`/`mutations.ts`) + UI state hooks |
| `src/components/`   | Reusable presentational components                  |
| `src/pages/`        | Route-level screens                                 |

## Pages

| Page        | Purpose                                                          |
| ----------- | ---------------------------------------------------------------- |
| Login       | Email + password sign-in                                         |
| Register    | Create an account (first user becomes admin)                     |
| Sources     | List/create/edit sources (name, adapter, base URL, config); test scrape |
| Searches    | Create a search: pick source + target, query URL + structured filters (keywords, location, workplace, salary) + |
|             | interval; enable/disable; run now (immediate results); view last |
|             | run, scrape errors, and recent delivery failures                 |
| Jobs        | Feed of seen jobs, filterable by search and status; mark seen/applied/archived; salary when scraped; copy RSS feed URL |
| Targets     | Manage notification targets (e.g. ntfy server/topic); send test  |
| Credentials | Per-source encrypted cookies/headers for bot-walled sites        |
| Settings    | API base URL, ntfy help                                          |
| Admin       | User management + global scrape/delivery stats (admin only)      |

## Auth flow

- Login/register store JWT access + refresh tokens in `localStorage`
- `/forgot-password` and `/reset-password?token=...` for email-based password reset
  (`src/lib/settings.ts`).
- `src/api/client.ts` attaches the access token to every request and, on a 401,
  tries `/auth/refresh` once before clearing the session.
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
- Covered pages: Sources, Searches, Targets, Jobs, Admin (render, empty state, list data,
  and primary actions like create/delete/test/run).

## Dev

- Standalone: `npm run dev` (Vite dev server on :5173, proxying to the API).
- In the stack: served by nginx on :8080 (see `frontend/Dockerfile`,
  `frontend/nginx.conf`). Service worker assets (`sw.js`, `manifest.webmanifest`)
  are served with `Cache-Control: no-cache` so updates propagate.

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
