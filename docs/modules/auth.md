# Module: Auth

**Paths:** `backend/app/core/security.py`, `backend/app/api/deps.py`,
`backend/app/services/auth.py`, `backend/app/api/v1/auth.py`,
`backend/app/schemas/auth.py`, `frontend/src/auth/`

Multi-user authentication with JWT access + refresh tokens and full per-user
data isolation.

## Model

- `user` table: `email` (unique), `password_hash` (bcrypt), `is_admin`,
  `is_active`, `plan` (`free` / `starter` / `plus` / `pro`, default `free`),
  `email_verified_at` (null until the user confirms their address). See
  [data-model.md](data-model.md).
- The **first** registered user becomes admin (`AuthService.register`). A
  `registration_lock` singleton row is claimed atomically
  (`bootstrap_claimed=True` plus `bootstrap_user_id`) so concurrent bootstrap
  registrations cannot create multiple admins. `bootstrap_claimed` is a
  permanent latch: deleting the bootstrap user may `SET NULL` the FK, but the
  latch stays set so a later registrant is never auto-promoted again.
- Every owned entity (`source`, `search`, `notification_target`,
  `site_credential`) carries a `user_id` FK. `seen_job` / `delivery_log` are
  scoped transitively through their parent `search`.

## Tokens

- `create_access_token` / `create_refresh_token` (PyJWT, `HS256`) sign a payload
  of `{sub: user_id, type, ver, iat, exp}` with `settings.jwt_secret`.
- Access tokens are short-lived (`ACCESS_TOKEN_EXPIRE_MINUTES`, default 30);
  refresh tokens last `REFRESH_TOKEN_EXPIRE_DAYS` (default 7).
- **Session revocation:** `ver` carries `user.token_version`. `get_current_user`
  (access) and `/refresh` reject any token whose `ver` no longer matches the
  user's current version, so bumping `token_version` invalidates every
  outstanding access **and** refresh token at once. Password reset bumps it (see
  below); `/logout` bumps it when a valid refresh token is presented; `/refresh`
  bumps it before issuing a new refresh cookie (rotation — a previously issued
  refresh JWT cannot be replayed). Admin deactivation (`PATCH /admin/users/{id}`
  with `is_active=false`) also bumps `token_version`, so a later reactivation
  cannot resurrect JWTs minted before the lock-out. RSS feed URLs use a separate
  `feed_token_version` claim; password reset bumps that too so leaked feed links
  stop working after credential recovery.
  Because pre-existing tokens carry no `ver`, they are treated as stale and
  forced to re-authenticate the first time this ships.
- **Token delivery:** `/login` and `/refresh` return the **access token in the
  response body** and set the **refresh token as an httpOnly cookie**
  (`AUTH_COOKIE_*`). The refresh token is never exposed to JavaScript, so XSS
  cannot exfiltrate the long-lived credential. `/refresh` reads the cookie (and
  rotates it by bumping `token_version`); `/logout` clears the cookie and bumps
  `token_version` when the refresh JWT is still valid. Non-browser clients may
  `refresh_token` in the `/refresh` body. See
  [adr/0007-httponly-refresh-cookie.md](../adr/0007-httponly-refresh-cookie.md).
- `decode_token(token, expected_type=...)` validates signature, expiry, and the
  `type` claim, raising `TokenError` otherwise.
- Passwords: `hash_password` / `verify_password` (bcrypt, input truncated to the
  72-byte bcrypt limit).

## Enforcement

`app.api.deps.get_current_user` reads `Authorization: Bearer <access>`, decodes
it, loads the active `User`, and 401s on any failure. **Every** v1 route (reads
and writes) depends on it. `get_current_admin` additionally requires
`is_admin`.

Services accept a `user_id` and scope every query to it; cross-user access
returns `NotFoundError` (404), never another user's data.

## Endpoints (prefix `/api/v1/auth`)

| Method | Path        | Auth   | Purpose                                |
| ------ | ----------- | ------ | -------------------------------------- |
| POST   | `/register` | none   | Create an account (first = admin)      |
| POST   | `/login`    | none   | Email+password → access token (body) + refresh cookie |
| POST   | `/refresh`  | none*  | Refresh cookie → new access token (rotates cookie) |
| POST   | `/logout`   | none   | Clear the refresh cookie and revoke the session |
| POST   | `/forgot-password` | none | Request a password-reset email   |
| POST   | `/reset-password`  | none | Set a new password from reset link |
| POST   | `/verify-email`    | none | Confirm email from verification link |
| POST   | `/resend-verification` | bearer | Send another verification email |
| GET    | `/me`       | bearer | Current user                           |
| POST   | `/me/complete-onboarding` | bearer | Mark the first-run wizard finished |
| GET    | `/me/export` | bearer | JSON bundle of all owned data (GDPR export) |
| DELETE | `/me`       | bearer | Permanently delete account (password in body) |

\* `/refresh` is unauthenticated but requires a valid refresh token, normally
read from the httpOnly cookie (falls back to a `refresh_token` body field).

## Rate limiting (AUT-03)

Unauthenticated and email-issuing auth routes are throttled in-process with a
sliding window (`app.core.rate_limit`). Exceeding a bucket returns **429**
`{"detail": "Too many requests. Try again later."}`.

| Route / action | Keys | Default ceiling |
| -------------- | ---- | --------------- |
| `POST /login` | client IP + email | 20 / 15 min (IP), 10 / 15 min (email) |
| `POST /register` | client IP | 10 / hour |
| `POST /forgot-password` | client IP + email | 10 / hour (IP), 5 / hour (email) |
| `POST /reset-password`, `POST /verify-email` | client IP | 20 / 15 min |
| `POST /resend-verification` | user id | 5 / hour |
| `POST /refresh` | client IP | 60 / 15 min |
| Outbound reset / verify email | email address | 5 / hour |

Counters are process-local (each API task enforces its own ceiling). Tests call
`reset_rate_limiter()` so suites do not leak 429s across cases.

## Security event logging (AUT-10)

Auth services emit structured INFO lines via `app.core.auth_events` (never
plaintext email or tokens). Each line is `auth_event=<name>` plus optional
`email_hash=` (HMAC fingerprint, same as GDPR audit pseudonyms), `user_id=`,
`ip=`, `reason=`, and `issued=`.

| Event | When |
| ----- | ---- |
| `login_success` / `login_failure` | Password check outcome (`reason=invalid_credentials` on fail) |
| `password_reset_requested` | Forgot-password (always; `issued=true` only when mail was sent) |
| `password_reset_completed` | Successful reset |
| `session_invalidated` | Logout or reset (`reason=logout` / `password_reset`) |
| `account_deleted` | Confirmed account erasure |

Failed logins also increment Prometheus `headstart_auth_login_failures_total`
(see [metrics.md](metrics.md)).

## Frontend

- `frontend/src/lib/settings.ts` keeps the **access token in memory only** (a
  module variable, never `localStorage`/`sessionStorage`). The refresh token is
  the httpOnly cookie owned by the backend and is invisible to JS.
- `frontend/src/api/client.ts` sends `credentials: "include"` on every request
  and attaches the in-memory access token. On a 401 it calls `refreshSession()`
  (cookie-based `/auth/refresh`) once, stores the new access token, and retries;
  if that fails it clears the token and notifies `AuthContext`.
- `frontend/src/auth/AuthContext.tsx` holds the current user. On load it calls
  `refreshSession()` to mint an access token from the cookie, then `/auth/me`;
  `logout()` calls `/auth/logout` to clear the cookie. `ProtectedRoute` gates
  the app and   redirects to `/login`. `OnboardingGuard` sends new accounts to
  `/app/onboarding` until `onboarding_completed_at` is set.
  `EmailVerificationGuard` sends unverified accounts to `/verify-email` before
  onboarding or the main app shell.
- `/forgot-password` and `/reset-password?token=...` handle the reset flow.
- `/verify-email` and `/verify-email?token=...` handle email verification after
  signup. Unverified users can sign in but product routes return **403** until
  verified; the UI redirects them to `/verify-email`. Account export/deletion
  (`/app/settings`) remains available before verification.
- **Settings → Your account** (`/app/settings`): export all owned data as JSON
  (`GET /auth/me/export`) or permanently delete the account (`DELETE /auth/me`
  with the current password). Deletion cascades to sources, searches, targets,
  credentials, profile, jobs, and delivery history. The sole remaining admin
  cannot delete their account while other users exist — promote another admin
  first.

## Password reset

1. User submits their email on `/forgot-password` → `POST /auth/forgot-password`.
2. If the account exists and is active, a single-use token is stored (hashed) and
   emailed. The API always returns the same success message (no email enumeration).
3. Token generation and hashing always run — including for unknown or inactive
   emails — so the miss path does not skip that work. The reset email is queued
   on FastAPI `BackgroundTasks` so the HTTP response does not wait on SMTP;
   response timing therefore cannot enumerate accounts via the mail round-trip
   (AUT-26). Direct service callers without a scheduler still send synchronously.
4. The email link opens `/reset-password?token=...` → `POST /auth/reset-password`
   with the token and new password.
5. Valid tokens are deleted after use; expired tokens are rejected.
6. The reset **bumps `token_version` and `feed_token_version`**, so any
   access/refresh token or RSS feed URL issued before the reset (e.g. one
   captured from a compromised session) immediately stops validating — the user
   must sign in again everywhere and re-issue feed links.

**Email delivery:** configure SMTP via `SMTP_*` env vars. When `SMTP_HOST` is
empty in `local`/`test`, the API logs the reset URL at INFO instead of sending
mail. Outside those environments `SMTP_HOST` is required at startup, and the
log fallback refuses to emit the token-bearing URL (AUT-01).

## Email verification

1. On register, a single-use token is stored (hashed) and emailed. Existing
   accounts created before this feature are grandfathered as verified.
2. The email link opens `/verify-email?token=...` → `POST /auth/verify-email`
   with the token.
3. Signed-in users can request another email via `POST /auth/resend-verification`.
4. Most API routes require a verified email (`403` otherwise). Auth self-service
   (`/me`, export, delete) and `/app/settings` stay available while unverified.

**Email delivery:** uses the same `SMTP_*` configuration as password reset. When
`SMTP_HOST` is empty in `local`/`test`, the verification URL is logged at INFO;
non-local environments require SMTP and never log the token.

## Account data export & deletion

Users can download a portable JSON export of everything they own
(`GET /auth/me/export`) — account, sources, searches, targets, site credentials
(including decrypted session material), application profile (with resume and
LaTeX template bytes), job history, application logs, generated artifacts
(decrypted), delivery logs, mailbox metadata (secrets redacted), inbox
classifications / reply drafts / pending replies / send logs, and promo
redemptions. `format_version` is `2`. Password hashes and live mailbox OAuth
tokens / IMAP passwords are never included.

Permanent account deletion (`DELETE /auth/me` with `{ "password": "..." }`)
requires the current password, clears the refresh cookie, and removes the user
row. Owned data cascades via ORM `delete-orphan` relationships on `User`
(including `application_artifact`, `promo_redemption`, and
`promo_validation_attempt`) plus DB `ON DELETE CASCADE`. Tests enable SQLite
`PRAGMA foreign_keys=ON` so both layers are exercised. The last admin account
cannot be deleted while other users remain (promote another admin first).

When Stripe is configured and the account has billing IDs, deletion first
cancels any `stripe_subscription_id` and deletes the `stripe_customer_id`
(best-effort: Stripe errors are logged and do not block local erasure).

Successful export and deletion requests are recorded in `data_request_log`.
Export rows keep the live email (and optional client IP / user agent) while the
account exists. On deletion, prior export rows for that user are redacted and
the deletion row stores only an HMAC email pseudonym (`erased:<hex>`) with no
IP or user agent — recoverable PII does not survive erasure (DAT-02). Admins
list recent rows via `GET /admin/data-requests`.

Public subprocessors and DPA overview: `/subprocessors` (linked from the privacy
policy and site footer). The list names AWS, Stripe, OpenAI, Google Gemini,
Anthropic, Gmail / Outlook / Yahoo mailbox OAuth, and SMTP so Art.28 disclosure
covers the shipped AI and inbox adapters (not only the original AWS/Stripe/OpenAI
set).

## Plan limits

Every account has a `plan` (`free`, `starter`, `plus`, or `pro`; default `free`).
Caps and feature gates are defined in `app/core/plans.py` (mirrors the public
pricing page) and enforced in `PlanLimitsService` — **services raise
`PlanLimitError`, mapped to HTTP 402**, never UI-only checks.

| Resource / feature | Free | Starter | Plus | Pro |
| ------------------ | ---- | ------- | ---- | --- |
| Searches | 3 | 5 | 10 | 20 |
| Sources | 3 | 5 | 10 | 20 |
| Notification targets | 1 | 2 | 3 | 5 |
| Pipeline auto-applies / rolling 24h | 3 | 5 | 10 | 20 |
| Digest mode | no | yes | yes | yes |
| Premium scrapers (`indeed`, `linkedin`, `playwright`) | no | no | yes | yes |
| Site credentials | no | no | yes | yes |
| AI summaries (pipeline) | no | no | no | yes |
| RSS feed | no | no | no | yes |
| Webhook notifier | no | no | no | yes |
| Cross-portal search (`/portals/search`) | no | no | no | yes |

**Downgrade behaviour:** existing rows stay; create/update that would exceed a
cap or use a gated feature is rejected. Admins bypass all limits. At **pipeline
consumption time**, premium scrapers and notifiers are re-checked: a downgraded
user's `indeed`/`linkedin`/`playwright` source skips the scrape (run records an
error and reschedules), and a `webhook` target skips delivery (immediate notify
and digest queue/flush). Pending digest rows for a disallowed notifier are
cleared without sending so they do not retry forever.

`GET /meta` returns an `AccountPlanRead` snapshot (limits, current usage,
feature flags including `portal_search`, allowed scrapers/notifiers) so the UI
can disable options proactively. `PlanFeaturesRead` mirrors
`core.plans.PlanFeatures` so snapshot keys are not dropped on serialize.
`PATCH /admin/users/{id}` accepts `plan` for manual overrides.

## Admin

Admins (`is_admin=true`, first registered user by default) can open `/admin` in
the UI. The page lists all accounts (activate/deactivate, grant/revoke admin,
change subscription `plan`) and shows global scrape health: search counts, delivery success/failure totals,
and recent scrape errors across all users. Admins cannot deactivate themselves,
remove their own admin flag, or demote the last remaining admin account.
Deactivating an account bumps `token_version` so outstanding sessions stay
revoked even if the account is later reactivated.

Every successful `PATCH /admin/users/{id}` that changes `is_active`, `is_admin`,
or `plan` emits a structured INFO audit line via `app.core.admin_events`
(`admin_event=user_update actor_id=… target_id=… before=… after=…`) so privilege
and plan mutations leave a server-side trail for incident response (BIL-01).
No-op patches (same values) do not log.

## Configuration

`JWT_SECRET`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`,
`PASSWORD_RESET_EXPIRE_MINUTES`, `EMAIL_VERIFICATION_EXPIRE_MINUTES`,
`FRONTEND_BASE_URL`, the refresh-cookie settings
`AUTH_COOKIE_NAME` / `AUTH_COOKIE_PATH` / `AUTH_COOKIE_SECURE` /
`AUTH_COOKIE_SAMESITE`, and optional `SMTP_*` (see `.env.example`). The cookie
defaults are production-safe (`Secure` + `SameSite=Lax`); for local dev over
plain HTTP set `AUTH_COOKIE_SECURE=false`. On AWS, Terraform sets
`AUTH_COOKIE_SECURE` from `https_enabled` in the ECS task environment (false on
the default HTTP ALB, true when TLS is configured); secrets such as `JWT_SECRET`
still come from Secrets Manager (see [deployment.md](deployment.md)).
