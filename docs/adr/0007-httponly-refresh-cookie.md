# 0007. httpOnly refresh-token cookie; access token in memory

- **Status:** Accepted
- **Date:** 2026-06-29

## Context

The SPA originally stored both the JWT access token and the long-lived refresh
token in `localStorage`. `localStorage` is readable by any JavaScript running on
the page, so a single XSS bug would leak the 7-day refresh token, letting an
attacker mint access tokens indefinitely. We want to shrink that blast radius
without abandoning the existing access/refresh JWT scheme or the simple
"static bundle behind nginx" deployment.

## Decision

- The **refresh token** is delivered as an **httpOnly, `SameSite`, optionally
  `Secure` cookie** scoped to the auth routes (`AUTH_COOKIE_*` settings). It is
  set by `/auth/login` and rotated by `/auth/refresh`, and cleared by the new
  `/auth/logout`. Being httpOnly, it is invisible to JavaScript.
- The **access token** is returned in the response body and held **only in
  memory** on the client (a module variable), never in `localStorage`/
  `sessionStorage`.
- On load (or after a hard refresh) the SPA calls `/auth/refresh`, which reads
  the cookie and returns a fresh access token; the API client also does this
  transparently on a 401, then retries the original request.
- `CORSMiddleware` already runs with `allow_credentials=True` and an explicit
  origin allow-list (never `*`), which is required for cookie auth.

## Consequences

- XSS can no longer read the refresh token; the worst it can do is ride the
  current in-memory access token until the tab closes.
- Cookie attributes are configurable. Production is same-origin behind nginx, so
  `Secure` + `SameSite=Lax` works; cross-site setups need `SameSite=None` +
  `Secure`. Local dev over plain HTTP sets `AUTH_COOKIE_SECURE=false`.
- The login response body no longer contains `refresh_token`; non-browser
  clients may still POST `refresh_token` in the `/auth/refresh` body.
- A full page reload now does a refresh round-trip before the UI resolves the
  user (one extra request), in exchange for not persisting any token in JS.

## Alternatives considered

- **Keep both tokens in `localStorage`** — simplest, but leaves the long-lived
  refresh token exposed to XSS. Rejected.
- **Both tokens in httpOnly cookies (cookie-only auth)** — would require sending
  the access token as a cookie too and add CSRF surface (state-changing requests
  authenticated by an ambient cookie). Keeping the access token in a `Bearer`
  header avoids CSRF for the API while still protecting the refresh token.
- **`sessionStorage` for the access token** — still JS-readable; in-memory is
  strictly better and the refresh cookie already restores sessions across
  reloads.
