# 0004. Multi-user accounts with JWT and per-user isolation

- **Status:** Accepted
- **Date:** 2026-06-28

## Context

HeadStart started single-user: one shared `API_AUTH_TOKEN` guarded write
endpoints and all data was global. We want multiple people to use one
deployment, each with their own sources, searches, notification targets, and
credentials, without seeing each other's data.

## Decision

- Add a `user` table (email + bcrypt `password_hash` + `is_admin` + `is_active`).
- Authenticate with **JWT**: short-lived access tokens plus refresh tokens
  (PyJWT, `HS256`, signed with `JWT_SECRET`). Replace the shared token entirely.
- Open self-registration; the **first** registered user becomes admin.
- Add a `user_id` FK to `source`, `search`, `notification_target`, and
  `site_credential`. `seen_job` / `delivery_log` stay scoped through their parent
  `search` (no redundant column).
- Enforce ownership in services/repositories: **every** API route (reads
  included) requires a valid access token and is scoped to that user; cross-user
  access returns 404.
- The Celery scheduler stays global (it selects due searches across all users);
  the pipeline resolves ownership from each search.

## Consequences

- Reads are no longer anonymous — the frontend must log in. Added an
  `AuthContext`, login/register pages, protected routes, and transparent
  refresh-on-401 in the API client.
- A new Alembic migration adds the tables/columns and backfills any pre-existing
  rows to a bootstrap admin so `user_id` can be `NOT NULL`.
- `JWT_SECRET` becomes a required secret in every environment (added to Terraform
  Secrets Manager; `API_AUTH_TOKEN` removed).

## Alternatives considered

- **Per-user long-lived API tokens only** — simplest, closest to the old model,
  but worse UX (manual token handling) and no real session/expiry story.
- **Server-side session cookies** — more XSS-resistant, but adds CSRF handling
  and server-side session storage; JWT keeps the API stateless and the SPA
  simple.
- **Shared global source catalog** — rejected; full per-user isolation is
  simpler to reason about and matches the "my own watchlist" mental model.
