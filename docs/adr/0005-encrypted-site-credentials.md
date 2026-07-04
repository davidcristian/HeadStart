# 0005. Encrypted per-site credentials injected into scrapers

- **Status:** Accepted
- **Date:** 2026-06-28

## Context

Some job portals hide listings behind a login or a bot/captcha wall. To watch
those sites we need to present a logged-in session. Longer term, the same
material enables auto-applying to jobs. Storing session cookies/headers is
sensitive and must not leak.

## Decision

- Add a `site_credential` entity owned by a `(user, source)` pair. It stores a
  JSON payload `{cookies, headers, session}` that is **Fernet-encrypted at rest**
  (`app.core.crypto`); only `secret_ciphertext` is persisted.
- Stretch the Fernet key from `CREDENTIALS_SECRET_KEY` with **scrypt** (fixed
  salt `headstart.credentials.v1`). `MultiFernet` also keeps the legacy
  unsalted-SHA-256 derivation of the current secret (pre-AUT-05 ciphertext) and
  an optional `CREDENTIALS_SECRET_KEY_PREVIOUS` so operators can rotate without
  bricking stored secrets. Non-local boots require length ≥ 32 and reject the
  built-in placeholder.
- Never return secret values over the API. `CredentialRead` exposes metadata and
  booleans (`has_cookies` / `has_headers` / `has_session`) only.
- Inject at the edge: `PipelineService` looks up the search owner's enabled
  credential for the source, decrypts it, and builds the shared `HttpClient` with
  those cookies/headers. Existing adapters need no changes; `ScrapeContext` also
  carries the cookies/headers for adapters that want them.
- **Scope now: storage + request injection only.** Auto-apply is explicitly
  deferred.

## Consequences

- Adds the `cryptography` dependency and a required `CREDENTIALS_SECRET_KEY`
  secret. Rotating it is supported via `CREDENTIALS_SECRET_KEY_PREVIOUS`
  (MultiFernet); dropping the previous value without re-encrypting makes old
  ciphertext unreadable.
- Credentials follow the same per-user isolation as everything else (ADR-0004).
- Provides a clean seam for future channels (auto-apply, authenticated APIs)
  without touching adapters.

## Alternatives considered

- **Store secrets in `search`/`source` config JSON** — simplest, but plaintext
  at rest and mixes secrets with non-secret config; rejected.
- **External secrets manager per credential** — overkill for per-user session
  cookies and couples local dev to cloud infra.
- **Encrypt with a per-user key** — stronger blast-radius isolation, but adds key
  management we don't need yet; a single app key is sufficient for now.
