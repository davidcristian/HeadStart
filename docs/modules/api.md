# Module: API

**Path:** `backend/app/api/`

FastAPI app exposing CRUD for the configurable entities plus a job feed and
health. Interactive docs at `/docs` (and `/redoc` / `/openapi.json`) are
enabled only when `ENVIRONMENT` is `local` or `test` (AUT-25); production
boots set those URLs to `None` so the public surface cannot be enumerated.

## Layering

Routers are thin: parse input -> call a **service** -> return a **schema**. They
never touch the DB directly (services use repositories). See
[AGENTS.md](../../AGENTS.md) §1.

## Endpoints (v1, prefix `/api/v1`)

| Method | Path                  | Purpose                                  |
| ------ | --------------------- | ---------------------------------------- |
| GET    | `/health`             | Liveness/readiness (public)              |
| GET    | `/meta`               | Plan limits, usage, allowed scrapers/notifiers |
| POST   | `/auth/register`      | Create an account (first = admin)        |
| POST   | `/auth/login`         | Exchange email+password for JWTs         |
| POST   | `/auth/refresh`       | Exchange a refresh token for new JWTs    |
| POST   | `/auth/logout`        | Clear the refresh cookie                 |
| POST   | `/auth/forgot-password` | Request a password-reset email         |
| POST   | `/auth/reset-password`  | Set a new password from reset link     |
| POST   | `/auth/verify-email`  | Confirm email from verification link     |
| POST   | `/auth/resend-verification` | Send another verification email (bearer) |
| GET    | `/auth/me`            | Current user                             |
| POST   | `/auth/me/complete-onboarding` | Mark the first-run wizard finished |
| GET    | `/auth/me/export`     | Export all owned data as JSON            |
| DELETE | `/auth/me`            | Permanently delete account (password)    |
| GET    | `/sources`            | List sources                             |
| POST   | `/sources`            | Create a source (site + adapter_key)     |
| POST   | `/sources/detect`     | Infer adapter + defaults from a careers URL |
| GET    | `/sources/{id}`       | Get a source                             |
| PATCH  | `/sources/{id}`       | Update a source                          |
| DELETE | `/sources/{id}`       | Delete a source                          |
| POST   | `/sources/{id}/test`  | Dry-run scrape; return sample postings   |
| GET    | `/portals`            | Curated employer portal catalog — see [portals.md](portals.md) |
| POST   | `/portals/search`     | Cross-portal job search (Pro+; `portal_search` feature) |
| POST   | `/portals/subscribe`  | Bulk create sources + searches for curated portals (Pro+) |
| GET    | `/searches`           | List searches                            |
| POST   | `/searches`           | Create a search (url, filters, interval, target) |
| GET    | `/searches/{id}`      | Get a search                             |
| PATCH  | `/searches/{id}`      | Update a search (enable/disable, retune) |
| DELETE | `/searches/{id}`      | Delete a search                          |
| POST   | `/searches/{id}/run`  | Queue the search pipeline (`status=queued`, HTTP 202). Poll `GET /search-runs/{id}` until `ready`/`failed`; response includes found/new/notified counts. |
| GET    | `/search-runs/{id}`   | Poll one queued manual search run until terminal status |
| GET    | `/jobs`               | Feed of seen jobs (filter by `search_id`, `status`) |
| PATCH  | `/jobs/{id}`          | Update triage status (`seen` / `applied` / `archived`) |
| POST   | `/jobs/{id}/apply`    | Submit or preview an auto-apply (`dry_run`, optional `cover_letter`, optional `tailored_resume_b64` or `tailored_resume_artifact_id`). Dry-run preview returns HTTP 200; live submit returns HTTP 202 with `status=queued` + `application_log_id` — poll `GET /application-logs/{id}`. |
| POST   | `/jobs/{id}/generate-cover-letter` | Queue a tailored cover letter (`status=queued`). Poll `GET /document-generations/{id}` until `ready`/`failed`; ready `result` has `cover_letter`, `provider`, `fallback`. |
| POST   | `/jobs/{id}/generate-resume` | Queue a tailored resume PDF (`status=queued`). Poll `GET /document-generations/{id}`; ready `result` has `pdf_b64`, `artifact_id`, `provider`, `fallback`, `injection_guarded`. Compiles in the worker with `tectonic`/`pdflatex` (`-no-shell-escape` + restricted env + POSIX `RLIMIT_AS`/`CPU`/`NPROC`). |
| GET    | `/document-generations/{id}` | Poll one queued resume/cover-letter generation until terminal status |
| GET    | `/application-logs` | List recent auto-apply attempts (`limit`, default 100) |
| GET    | `/application-logs/{id}` | Poll one queued/live apply log until terminal status |
| GET    | `/application-artifacts/{id}` | Metadata for one stored generated document (owner only) |
| GET    | `/application-artifacts/{id}/download` | Download decrypted artifact bytes (e.g. tailored resume PDF) |
| GET    | `/applications` | Application pipeline rows (`stage` filter optional): job + derived `pipeline_stage`, `latest_attempt`, chronological `attempts`. Stage derivation maps archived/closed/rejected/interview_pending/ghosted/queued/apply_failed explicitly; everything else (including applied/submitted) is `awaiting_reply` (SVC-10) |
| GET    | `/feed/url`           | Signed RSS feed URL for the current user             |
| POST   | `/feed/rotate`        | Invalidate prior feed URLs and issue a new one       |
| GET    | `/feed/rss`           | RSS 2.0 job feed (public; `token` query **or** `Authorization: Bearer`). Missing/invalid token → `UnauthorizedError` (401); plan gate raises `PlanLimitError` (402 with `code`/`plan`/`limit`) via the central handlers — not local `HTTPException`. |
| GET    | `/targets`            | List notification targets                |
| POST   | `/targets`            | Create a target; per-type `config` validated (required keys + SSRF-safe URLs; API-14) |
| PATCH  | `/targets/{id}`       | Update a target (re-validates effective type+config) |
| DELETE | `/targets/{id}`       | Delete a target                          |
| POST   | `/targets/{id}/test`  | Send a test notification                 |
| GET    | `/credentials`        | List site credentials (metadata only)    |
| POST   | `/credentials`        | Create encrypted site credentials        |
| PATCH  | `/credentials/{id}`   | Update credential                        |
| DELETE | `/credentials/{id}`   | Delete credential                        |
| GET    | `/profile`            | Get the application profile (empty defaults if unset) |
| PUT    | `/profile`            | Create or fully replace the application profile text fields |
| PUT    | `/profile/resume`     | Upload or replace resume file (multipart `file`) |
| DELETE | `/profile/resume`     | Clear resume file only; HTTP **200** + `ProfileRead` (state-returning; other DELETEs are 204) |
| PUT    | `/profile/resume-template` | Upload or replace LaTeX resume template (multipart `file`) |
| DELETE | `/profile/resume-template` | Clear LaTeX template only; HTTP **200** + `ProfileRead` (same state-returning contract) |
| DELETE | `/profile`            | Clear the application profile (HTTP 204) |
| GET    | `/admin/users`        | List all users (admin only)              |
| PATCH  | `/admin/users/{id}`   | Toggle `is_active` / `is_admin` / `plan` (admin; structured `admin_event=user_update` audit log) |
| GET    | `/admin/stats`        | Global scrape/delivery aggregates (admin)|
| GET    | `/admin/data-requests` | Recent GDPR export/deletion audit rows (admin; `limit` Query `ge=1,le=500`, default 100; deletion rows are email-pseudonymized) |
| GET    | `/admin/promo-codes`  | List promo codes (admin)                 |
| POST   | `/admin/promo-codes`  | Create a promo code (admin)              |
| PATCH  | `/admin/promo-codes/{id}` | Update a promo code (admin)          |
| GET    | `/admin/promo-codes/{id}/redemptions` | List redemptions for a code (admin) |
| GET    | `/billing/status`     | Billing capabilities + subscription state |
| POST   | `/billing/checkout`   | Start Stripe Checkout for a paid plan    |
| POST   | `/billing/promo/validate` | Validate a promo code for checkout |
| POST   | `/billing/portal`     | Open Stripe customer portal              |
| POST   | `/billing/webhook`    | Stripe subscription webhooks (signed)    |

`SearchRead` includes scrape health: `last_run_at`, `last_error` (most recent
scrape failure), and `recent_delivery_failures` (up to five recent failed
notification attempts with job title, URL, error, and timestamp). The failures
list is ranked in SQL per search (`ROW_NUMBER()` over `sent_at`) so listing
searches never materializes a search's full `delivery_log` failure history.

## Auth

Multi-user with JWT. **Public** routes (no bearer token): `/health`,
`/feed/rss`, `/billing/webhook`, and `/auth/register`, `/auth/login`,
`/auth/refresh`, `/auth/logout`, `/auth/forgot-password`, `/auth/reset-password`,
and `/auth/verify-email`.

All other routes require `Authorization: Bearer <access_token>` and are
**scoped to the authenticated user** — including reads. Cross-user access returns
404. Most product routes additionally require a **verified email** (`403` until
`email_verified_at` is set); auth self-service (`/auth/me`, export, delete) and
settings remain available while unverified. Full detail in [auth.md](auth.md);
decisions in [adr/0004-multi-user-accounts.md](../adr/0004-multi-user-accounts.md).

`/admin/*` routes additionally require `is_admin` and return 403 for non-admins.
They expose cross-user data (user list, global stats) intentionally.

**List `limit` / cursor query params** declare FastAPI `Query(ge=…, le=…)` so
out-of-bounds values return **422** and appear in OpenAPI. List resources share
one cap (`ge=1, le=500`): jobs, applications, application-logs, feed, admin
data-requests, and inbox classifications / reply-drafts / reply-send-logs.
`GET /inbox/messages` keeps a tighter live-mailbox fetch cap (`since_uid` ≥1
optional, `limit` 1–100). Do not clamp unbounded ints in the handler body.

Auth abuse endpoints (`/auth/login`, `/register`, `/forgot-password`,
`/reset-password`, `/verify-email`, `/resend-verification`, `/refresh`) return
**429** when their per-IP / per-email / per-user sliding windows are exceeded —
see [auth.md](auth.md#rate-limiting-aut-03).

## Request correlation id (AUT-15)

Every HTTP response includes an `X-Request-ID` header. Clients may send their
own `X-Request-ID` (letters, digits, `.`, `_`, `-`; max 128 chars); otherwise
the API mints a UUID4. The active id is bound via a contextvar and appears on
every log line as the `request_id` JSON field (or `[request_id]` when
`LOG_FORMAT=text`) so interleaved API output can be filtered to one request.
Celery workers bind the same field to the task id for the duration of each
task (see [worker.md](worker.md#request-correlation-id-aut-15)).

## Security response headers (AUT-23)

`SecurityHeadersMiddleware` stamps every API response (including CORS
preflight) with:

| Header | Value |
| ------ | ----- |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Content-Security-Policy` | `frame-ancestors 'none'` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` outside `local`/`test` |

HSTS is omitted in `local`/`test` so browsers do not pin plain-HTTP localhost.
The SPA nginx shell sets the same baseline (see [frontend.md](frontend.md));
the API is a separate origin behind the ALB and needs its own middleware.

## Interactive OpenAPI docs (AUT-25)

`create_app()` enables FastAPI's `/docs`, `/redoc`, and `/openapi.json` only
when `ENVIRONMENT` is `local` or `test`. Outside those environments the three
URLs are `None` (404), the root payload omits the `docs` link, and the ALB
forwards only `/api/*` to the API target group so `/docs` hits the SPA instead
of exposing the schema.

## Structured JSON logs (AUT-16)

`configure_logging()` defaults to one JSON object per stdout line
(`LOG_FORMAT=json`): `timestamp`, `level`, `logger`, `request_id`, `message`,
plus any logger `extra` fields (auth/admin audit events attach
`auth_event` / `admin_event`, `user_id`, `ip`, `before`/`after`, …). Set
`LOG_FORMAT=text` for the legacy human-readable line format during local
debugging. Invalid values fail settings validation at boot.

## Adding an endpoint

See [../recipes.md](../recipes.md) → "add an API endpoint".
