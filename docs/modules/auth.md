# Module: Auth

**Paths:** `backend/app/core/security.py`, `backend/app/api/deps.py`,
`backend/app/services/auth.py`, `backend/app/api/v1/auth.py`,
`backend/app/schemas/auth.py`, `frontend/src/auth/`

Multi-user authentication with JWT access + refresh tokens and full per-user
data isolation.

## Model

- `user` table: `email` (unique), `password_hash` (bcrypt), `is_admin`,
  `is_active`. See [data-model.md](data-model.md).
- The **first** registered user becomes admin (`AuthService.register`).
- Every owned entity (`source`, `search`, `notification_target`,
  `site_credential`) carries a `user_id` FK. `seen_job` / `delivery_log` are
  scoped transitively through their parent `search`.

## Tokens

- `create_access_token` / `create_refresh_token` (PyJWT, `HS256`) sign a payload
  of `{sub: user_id, type, iat, exp}` with `settings.jwt_secret`.
- Access tokens are short-lived (`ACCESS_TOKEN_EXPIRE_MINUTES`, default 30);
  refresh tokens last `REFRESH_TOKEN_EXPIRE_DAYS` (default 7).
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
| POST   | `/login`    | none   | Exchange email+password for tokens     |
| POST   | `/refresh`  | none*  | Exchange a refresh token for new tokens|
| GET    | `/me`       | bearer | Current user                           |

\* `/refresh` is unauthenticated but requires a valid refresh token in the body.

## Frontend

- `frontend/src/lib/settings.ts` stores access + refresh tokens in
  `localStorage`.
- `frontend/src/api/client.ts` attaches the access token to every request and,
  on a 401, transparently tries `/auth/refresh` once before clearing the session
  and notifying `AuthContext`.
- `frontend/src/auth/AuthContext.tsx` holds the current user; `ProtectedRoute`
  gates the app and redirects to `/login`.

## Configuration

`JWT_SECRET`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` (see
`.env.example`). In AWS these come from Secrets Manager (see
[deployment.md](deployment.md)).
