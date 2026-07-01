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
`secret_ciphertext` ever reaches the database. The encryption key is derived
from `CREDENTIALS_SECRET_KEY` (any string is hashed into a valid Fernet key).

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

This module covers **storage + request injection only**. Auto-apply (submitting
applications) is intentionally out of scope for now; see
[adr/0005-encrypted-site-credentials.md](../adr/0005-encrypted-site-credentials.md).
