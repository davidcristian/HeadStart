# Module: API

**Path:** `backend/app/api/`

FastAPI app exposing CRUD for the configurable entities plus a job feed and
health. Interactive docs at `/docs`.

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
| POST   | `/searches/{id}/run`  | Run the search pipeline immediately (returns found/new/notified counts) |
| GET    | `/jobs`               | Feed of seen jobs (filter by `search_id`, `status`) |
| PATCH  | `/jobs/{id}`          | Update triage status (`seen` / `applied` / `archived`) |
| POST   | `/jobs/{id}/apply`    | Submit or preview an auto-apply (`dry_run`, optional `cover_letter`, optional `tailored_resume_b64` or `tailored_resume_artifact_id`). Live submit returns `queued` + `application_log_id`; poll `GET /application-logs/{id}`. |
| POST   | `/jobs/{id}/generate-cover-letter` | Draft a tailored cover letter from the job + application profile (`provider`, `fallback`). Pro users use the effective `SUMMARY_PROVIDER`; others get the offline heuristic generator. |
| POST   | `/jobs/{id}/generate-resume` | Generate a tailored resume PDF from the LaTeX template + profile (`pdf_b64`, `artifact_id`, `provider`, `fallback`). Persists the PDF in `application_artifact` (SHA-256 dedup). Requires `tectonic` or `pdflatex` locally to compile. |
| GET    | `/application-logs` | List recent auto-apply attempts (`limit`, default 100) |
| GET    | `/application-logs/{id}` | Poll one queued/live apply log until terminal status |
| GET    | `/application-artifacts/{id}` | Metadata for one stored generated document (owner only) |
| GET    | `/application-artifacts/{id}/download` | Download decrypted artifact bytes (e.g. tailored resume PDF) |
| GET    | `/applications` | Application pipeline rows (`stage` filter optional): job + derived `pipeline_stage`, `latest_attempt`, chronological `attempts` |
| GET    | `/feed/url`           | Signed RSS feed URL for the current user             |
| POST   | `/feed/rotate`        | Invalidate prior feed URLs and issue a new one       |
| GET    | `/feed/rss`           | RSS 2.0 job feed (public; `token` query param)     |
| GET    | `/targets`            | List notification targets                |
| POST   | `/targets`            | Create a target (e.g. ntfy topic)        |
| PATCH  | `/targets/{id}`       | Update a target                          |
| DELETE | `/targets/{id}`       | Delete a target                          |
| POST   | `/targets/{id}/test`  | Send a test notification                 |
| GET    | `/credentials`        | List site credentials (metadata only)    |
| POST   | `/credentials`        | Create encrypted site credentials        |
| PATCH  | `/credentials/{id}`   | Update credential                        |
| DELETE | `/credentials/{id}`   | Delete credential                        |
| GET    | `/profile`            | Get the application profile (empty defaults if unset) |
| PUT    | `/profile`            | Create or fully replace the application profile text fields |
| PUT    | `/profile/resume`     | Upload or replace resume file (multipart `file`) |
| DELETE | `/profile/resume`     | Remove the stored resume file only |
| DELETE | `/profile`            | Clear the application profile            |
| GET    | `/admin/users`        | List all users (admin only)              |
| PATCH  | `/admin/users/{id}`   | Toggle `is_active` / `is_admin` / `plan` (admin) |
| GET    | `/admin/stats`        | Global scrape/delivery aggregates (admin)|
| GET    | `/admin/data-requests` | Recent GDPR export/deletion audit rows (admin) |
| GET    | `/admin/promo-codes`  | List promo codes (admin)                 |
| POST   | `/admin/promo-codes`  | Create a promo code (admin)              |
| PATCH  | `/admin/promo-codes/{id}` | Update a promo code (admin)          |
| GET    | `/admin/promo-codes/{id}/redemptions` | List redemptions for a code (admin) |
| GET    | `/billing/status`     | Billing capabilities + subscription state |
| POST   | `/billing/checkout`   | Start Stripe Checkout for Pro            |
| POST   | `/billing/promo/validate` | Validate a promo code for checkout |
| POST   | `/billing/portal`     | Open Stripe customer portal              |
| POST   | `/billing/webhook`    | Stripe subscription webhooks (signed)    |

`SearchRead` includes scrape health: `last_run_at`, `last_error` (most recent
scrape failure), and `recent_delivery_failures` (up to five recent failed
notification attempts with job title, URL, error, and timestamp).

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

## Adding an endpoint

See [../recipes.md](../recipes.md) → "add an API endpoint".
