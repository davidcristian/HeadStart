# Module: Auth

**Paths:** `backend/app/core/security.py`, `backend/app/api/deps.py`,
`backend/app/services/auth.py`, `backend/app/api/v1/auth.py`,
`backend/app/schemas/auth.py`, `frontend/src/auth/`

Multi-user authentication with JWT access + refresh tokens and full per-user
data isolation.

## Model

- `user` table: `email` (unique), `password_hash` (bcrypt), `is_admin`,
  `is_active`, `plan` (`free` / `pro` / `team`, default `free`),
  `email_verified_at` (null until the user confirms their address). See
  [data-model.md](data-model.md).
- The **first** registered user becomes admin (`AuthService.register`). A
  `registration_lock.bootstrap_user_id` column is claimed atomically so
  concurrent bootstrap registrations cannot create multiple admins.
- Every owned entity (`source`, `search`, `notification_target`,
  `site_credential`) carries a `user_id` FK. `seen_job` / `delivery_log` are
  scoped transitively through their parent `search`.

## Tokens

- `create_access_token` / `create_refresh_token` (PyJWT, `HS256`) sign a payload
  of `{sub: user_id, type, iat, exp}` with `settings.jwt_secret`.
- Access tokens are short-lived (`ACCESS_TOKEN_EXPIRE_MINUTES`, default 30);
  refresh tokens last `REFRESH_TOKEN_EXPIRE_DAYS` (default 7).
- **Token delivery:** `/login` and `/refresh` return the **access token in the
  response body** and set the **refresh token as an httpOnly cookie**
  (`AUTH_COOKIE_*`). The refresh token is never exposed to JavaScript, so XSS
  cannot exfiltrate the long-lived credential. `/refresh` reads the cookie (and
  rotates it); `/logout` clears it. Non-browser clients may still pass
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
| POST   | `/logout`   | none   | Clear the refresh cookie               |
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
3. The email link opens `/reset-password?token=...` → `POST /auth/reset-password`
   with the token and new password.
4. Valid tokens are deleted after use; expired tokens are rejected.

**Email delivery:** configure SMTP via `SMTP_*` env vars. When `SMTP_HOST` is
empty (typical local dev), the API logs the reset URL at INFO instead of sending
mail.

## Email verification

1. On register, a single-use token is stored (hashed) and emailed. Existing
   accounts created before this feature are grandfathered as verified.
2. The email link opens `/verify-email?token=...` → `POST /auth/verify-email`
   with the token.
3. Signed-in users can request another email via `POST /auth/resend-verification`.
4. Most API routes require a verified email (`403` otherwise). Auth self-service
   (`/me`, export, delete) and `/app/settings` stay available while unverified.

**Email delivery:** uses the same `SMTP_*` configuration as password reset. When
`SMTP_HOST` is empty, the verification URL is logged at INFO.

## Account data export & deletion

Users can download a portable JSON export of everything they own (`GET
site credentials (including decrypted session material), application profile, and
job history. Password hashes are never included.

Permanent account deletion (`DELETE /auth/me` with `{ "password": "..." }`)
requires the current password, clears the refresh cookie, and removes the user
row. Owned data cascades via FK/`ON DELETE CASCADE`. The last admin account
cannot be deleted while other users remain (promote another admin first).

Successful export and deletion requests are recorded in `data_request_log`
(user email snapshot, request type, client IP, user agent). Export rows keep
`user_id`; deletion rows store only the email because the account is removed
immediately afterward. Admins list recent rows via `GET /admin/data-requests`.

Public subprocessors and DPA overview: `/subprocessors` (linked from the privacy
policy and site footer).

## Plan limits

Every account has a `plan` (`free`, `pro`, or `team`; default `free`). Caps and
feature gates are defined in `app/core/plans.py` (mirrors the public pricing
page) and enforced in `PlanLimitsService` — **services raise `PlanLimitError`,
mapped to HTTP 402**, never UI-only checks.

| Resource / feature | Free | Pro | Team |
| ------------------ | ---- | --- | ---- |
| Searches | 3 | 15 | 50 |
| Sources | 3 | 15 | 50 |
| Notification targets | 1 | 5 | 20 |
| Digest mode | no | yes | yes |
| AI summaries (pipeline) | no | yes | yes |
| Site credentials | no | yes | yes |
| RSS feed | no | yes | yes |
| Premium scrapers (`indeed`, `linkedin`, `playwright`) | no | yes | yes |
| Webhook notifier | no | yes | yes |

**Downgrade behaviour:** existing rows stay; create/update that would exceed a
cap or use a gated feature is rejected. Admins bypass all limits.

`GET /meta` returns an `AccountPlanRead` snapshot (limits, current usage,
allowed scrapers/notifiers) so the UI can disable options proactively.
`PATCH /admin/users/{id}` accepts `plan` until Stripe billing ships.

## Admin

Admins (`is_admin=true`, first registered user by default) can open `/admin` in
the UI. The page lists all accounts (activate/deactivate, grant/revoke admin,
change subscription `plan`) and shows global scrape health: search counts, delivery success/failure totals,
and recent scrape errors across all users. Admins cannot deactivate themselves,
remove their own admin flag, or demote the last remaining admin account.

## Configuration

`JWT_SECRET`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`,
`PASSWORD_RESET_EXPIRE_MINUTES`, `EMAIL_VERIFICATION_EXPIRE_MINUTES`,
`FRONTEND_BASE_URL`, the refresh-cookie settings
`AUTH_COOKIE_NAME` / `AUTH_COOKIE_PATH` / `AUTH_COOKIE_SECURE` /
`AUTH_COOKIE_SAMESITE`, and optional `SMTP_*` (see `.env.example`). The cookie
defaults are production-safe (`Secure` + `SameSite=Lax`); for local dev over
plain HTTP set `AUTH_COOKIE_SECURE=false`. In AWS these come from Secrets
Manager (see [deployment.md](deployment.md)).
