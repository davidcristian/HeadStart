# Module: Site credentials

**Paths:** `backend/app/models/site_credential.py`,
`backend/app/core/crypto.py`, `backend/app/services/credentials.py`,
`backend/app/repositories/credentials.py`, `backend/app/api/v1/credentials.py`,
`frontend/src/pages/CredentialsPage.tsx`

Per-user, per-source secrets (cookies / headers / session) that the scraper
injects into requests, so a search can read sites that sit behind a login or a
bot/captcha wall. This is also the foundation for future auto-apply.

## What is stored

A `site_credential` row belongs to a `user` and a `source`. The secret payload
is a JSON object:

```json
{ "cookies": { "sessionid": "..." }, "headers": { "Authorization": "Bearer ..." }, "session": {} }
```

It is **Fernet-encrypted before storage** (`core.crypto.encrypt`); only
`secret_ciphertext` ever reaches the database. The encryption key is stretched
from `CREDENTIALS_SECRET_KEY` via **scrypt** (fixed app salt
`headstart.credentials.v1`). Encrypt always uses the scrypt-derived primary;
decrypt also accepts the legacy unsalted-SHA-256 derivation of the same secret
(so pre-upgrade ciphertext stays readable) and an optional
`CREDENTIALS_SECRET_KEY_PREVIOUS` for key rotation. Non-local boots require the
primary secret to be at least 32 characters (and not the built-in placeholder).

## Read safety

`CredentialRead` never returns secret values. It exposes metadata plus booleans
(`has_cookies`, `has_headers`, `has_session`). To change a secret, save the
credential again with new values.

## Injection into scrapers

`PipelineService._scrape` looks up the search owner's **enabled** credential for
the search's source (`CredentialService.secret_for_source`), decrypts it, and:

1. Builds an `HttpClient(headers=..., cookies=...)` passed to the scraper, and
2. Populates `ScrapeContext.cookies` / `.headers` for adapters that want them.

Existing adapters need **no changes** — the shared HTTP client carries the
cookies/headers automatically. If no credential exists, behavior is unchanged.

For **Greenhouse auto-apply**, store a Job Board API key in the credential
`session` object as `job_board_api_key` (see [appliers.md](appliers.md)). The
key is employer-issued; it is encrypted like other credential material.

For **Lever auto-apply**, store a Postings API key in the credential `session`
as `postings_api_key`.

For **Workday auto-apply**, store `CALYPSO_SESSION` and `CALYPSO_CSRF_TOKEN`
cookies from a logged-in apply page (see [appliers.md](appliers.md)). The
session is candidate-owned, not employer-issued.

For **Google Careers auto-apply**, store logged-in Google account cookies
(`SID`, `SAPISID`, `__Secure-1PSID`, …) plus the CSRF token from an
authenticated apply page in credential `session.at` (or `session.csrf_token`).
The session is candidate-owned, not employer-issued.

For **Microsoft Careers auto-apply**, store logged-in session cookies from
`apply.careers.microsoft.com` plus optional `session.csrf_token` from the apply
page meta tag `_csrf`. The session is candidate-owned, not employer-issued.

For **LinkedIn auto-apply**, store logged-in session cookies (`li_at`,
`JSESSIONID`) from linkedin.com. Optional `session.csrf_token` overrides the
CSRF header when Voyager requests fail with CSRF errors. The session is
candidate-owned, not employer-issued. See [appliers.md](appliers.md).

For **SmartRecruiters auto-apply**, store an Application API token in credential
`session.smart_token` (`X-SmartToken` header) or an OAuth bearer token in
`session.access_token`. Tokens are partner/employer-issued via the SmartRecruiters
developer portal — see [appliers.md](appliers.md).

## Endpoints (prefix `/api/v1/credentials`)

| Method | Path    | Purpose                                  |
| ------ | ------- | ---------------------------------------- |
| GET    | ``      | List the user's credentials (metadata)   |
| POST   | ``      | Create (encrypts cookies/headers/session)|
| GET    | `/{id}` | Get one (metadata)                       |
| PATCH  | `/{id}` | Update name/enabled and/or replace secret|
| DELETE | `/{id}` | Delete                                   |

All routes require auth and are scoped to the current user.

## How a user obtains cookies/headers

Log into the target site in a browser, open dev tools, and copy the relevant
session cookies (and any required headers) into the **Site credentials** form as
JSON. Treat these as passwords.

## Scope

This module covers **storage + request injection** for scrapers and apply
adapters. See [appliers.md](appliers.md) for supported auto-apply flows and
[adr/0005-encrypted-site-credentials.md](../adr/0005-encrypted-site-credentials.md).
