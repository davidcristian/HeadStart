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
| POST   | `/auth/register`      | Create an account (first = admin)        |
| POST   | `/auth/login`         | Exchange email+password for JWTs         |
| POST   | `/auth/refresh`       | Exchange a refresh token for new JWTs    |
| POST   | `/auth/forgot-password` | Request a password-reset email         |
| POST   | `/auth/reset-password`  | Set a new password from reset link     |
| GET    | `/auth/me`            | Current user                             |
| GET    | `/sources`            | List sources                             |
| POST   | `/sources`            | Create a source (site + adapter_key)     |
| GET    | `/sources/{id}`       | Get a source                             |
| PATCH  | `/sources/{id}`       | Update a source                          |
| DELETE | `/sources/{id}`       | Delete a source                          |
| POST   | `/sources/{id}/test`  | Dry-run scrape; return sample postings   |
| GET    | `/searches`           | List searches                            |
| POST   | `/searches`           | Create a search (url, filters, interval, target) |
| GET    | `/searches/{id}`      | Get a search                             |
| PATCH  | `/searches/{id}`      | Update a search (enable/disable, retune) |
| DELETE | `/searches/{id}`      | Delete a search                          |
| POST   | `/searches/{id}/run`  | Run the search pipeline immediately (returns found/new/notified counts) |

`SearchRead` includes scrape health: `last_run_at`, `last_error` (most recent
scrape failure), and `recent_delivery_failures` (up to five recent failed
notification attempts with job title, URL, error, and timestamp).
| GET    | `/jobs`               | Feed of seen jobs (filter by `search_id`, `status`) |
| PATCH  | `/jobs/{id}`          | Update triage status (`seen` / `applied` / `archived`) |
| GET    | `/targets`            | List notification targets                |
| POST   | `/targets`            | Create a target (e.g. ntfy topic)        |
| PATCH  | `/targets/{id}`       | Update a target                          |
| DELETE | `/targets/{id}`       | Delete a target                          |
| POST   | `/targets/{id}/test`  | Send a test notification                 |
| GET    | `/credentials`        | List site credentials (metadata only)    |
| POST   | `/credentials`        | Create encrypted site credentials        |
| PATCH  | `/credentials/{id}`   | Update credential                        |
| DELETE | `/credentials/{id}`   | Delete credential                        |
| GET    | `/admin/users`        | List all users (admin only)              |
| PATCH  | `/admin/users/{id}`   | Toggle `is_active` / `is_admin` (admin)  |
| GET    | `/admin/stats`        | Global scrape/delivery aggregates (admin)|

## Auth

Multi-user with JWT. **Every** route except `/health` and the
`/auth/register|login|refresh|forgot-password|reset-password` endpoints requires
`Authorization: Bearer <access_token>` and is **scoped to the authenticated
user** — including reads. Cross-user access returns 404. Full detail in
[auth.md](auth.md); decisions in
[adr/0004-multi-user-accounts.md](../adr/0004-multi-user-accounts.md).

`/admin/*` routes additionally require `is_admin` and return 403 for non-admins.
They expose cross-user data (user list, global stats) intentionally.

## Adding an endpoint

See [../recipes.md](../recipes.md) → "add an API endpoint".
