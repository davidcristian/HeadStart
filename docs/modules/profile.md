# Module: Application profile

**Paths:** `backend/app/models/application_profile.py`,
`backend/app/core/crypto.py`, `backend/app/schemas/profile.py`,
`backend/app/repositories/profiles.py`, `backend/app/services/profiles.py`,
`backend/app/api/v1/profile.py`, `frontend/src/pages/ProfilePage.tsx`

The candidate data an **auto-apply** flow needs to submit applications on the
user's behalf. This is the first piece of [Phase 7 — Auto-apply](../roadmap.md);
it covers **storage only**. Submitting applications (apply adapters,
orchestration) is intentionally out of scope here.

## What is stored

Exactly **one profile per user** (a singleton, `unique` on `user_id`). The
payload is a JSON object:

```json
{
  "full_name": "Ada Lovelace",
  "email": "ada@example.com",
  "phone": "+1 555 0100",
  "location": "London, UK",
  "links": { "linkedin": "", "github": "https://github.com/ada", "website": "" },
  "resume_text": "Pioneering programmer...",
  "cover_letter_template": "Dear {company} team, ...",
  "answers": { "work_authorization": "UK citizen", "notice_period": "2 weeks" }
}
```

`answers` is a free-form map of recurring application questions to the user's
canned response.

## Encryption & read safety

The whole payload is **Fernet-encrypted before storage** (`core.crypto.encrypt`,
keyed by `CREDENTIALS_SECRET_KEY`); only `data_ciphertext` reaches the database.
The profile is PII, not a shared secret like a login cookie, so — unlike
[site credentials](credentials.md) — the decrypted profile **is returned to its
owner** so it can be reviewed and edited in the UI. It is never exposed to other
users (every route is scoped to `get_current_user`).

`ProfileRead` adds two fields on top of the stored data:

- `exists` — `false` when the user has never saved a profile (the API returns
  empty defaults rather than a 404), so the UI can tell an empty default apart
  from a deliberately-cleared profile.
- `updated_at` — when the profile was last saved.

## Endpoints (prefix `/api/v1/profile`)

| Method | Path | Purpose                                            |
| ------ | ---- | -------------------------------------------------- |
| GET    | ``   | Get the profile (empty defaults if never saved)    |
| PUT    | ``   | Create or **fully replace** the profile            |
| DELETE | ``   | Clear the profile (idempotent)                     |

`PUT` is a whole-profile replacement (not a partial patch); the UI always sends
the complete form. All routes require auth and are scoped to the current user.

## Scope

Storage + retrieval only. The apply adapters, orchestration service, and the
"Apply" action on the Jobs page are tracked separately in
[roadmap.md → Phase 7](../roadmap.md). See
[adr/0008-application-profile.md](../adr/0008-application-profile.md) for the
decision record.
