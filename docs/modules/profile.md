# Module: Application profile

**Paths:** `backend/app/models/application_profile.py`,
`backend/app/core/crypto.py`, `backend/app/schemas/profile.py`,
`backend/app/repositories/profiles.py`, `backend/app/services/profiles.py`,
`backend/app/api/v1/profile.py`, `frontend/src/pages/ProfilePage.tsx`

The candidate data an **auto-apply** flow needs to submit applications on the
user's behalf. Storage and retrieval live here; [apply adapters](appliers.md)
read the decrypted profile at submit time. See [Phase 7 — Auto-apply](../roadmap.md)
for orchestration and per-site apply behavior.

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
  "answers": { "work_authorization": "UK citizen", "notice_period": "2 weeks" },
  "work_experience": [
    {
      "job_title": "Software Engineer",
      "company": "ACME Corp",
      "location": "Remote",
      "start_month": 3,
      "start_year": 2020,
      "end_month": 6,
      "end_year": 2023,
      "is_current": false,
      "description": "Built APIs and services."
    }
  ],
  "education": [
    {
      "school": "Example University",
      "degree": "Bachelor of Science",
      "field_of_study": "Computer Science",
      "start_year": 2016,
      "end_year": 2020,
      "gpa": "3.8"
    }
  ],
  "skills": ["Python", "SQL", "Distributed systems"],
  "languages": [
    {
      "language": "English",
      "proficiency": "Native",
      "is_native": true
    }
  ]
}
```

Optional **resume file** (PDF or Word, up to `PROFILE_RESUME_MAX_BYTES`, default 2 MB) is
stored in the same encrypted blob as base64 alongside the JSON fields above. The API
returns only metadata (`filename`, `content_type`, `size_bytes`) — never raw bytes on
`GET /profile`. On live apply, the file is attached for Greenhouse, Lever, Ashby,
Workday, Google Careers, Microsoft Careers, Amazon Jobs, Apple Careers, and Meta
Careers. LinkedIn-hosted and Indeed-hosted Easy Apply use `resume_text` only today
(see [appliers.md](appliers.md)).

`answers` is a free-form map of recurring application questions to the user's
canned response.

`work_experience` and `education` are structured lists used by the Workday
apply adapter (and future apply adapters). Each work-experience row needs a job
title, company, and start month/year; education rows need at least a school
name.

`skills` is a list of skill names (up to 100 entries, 200 characters each).
`languages` is a structured list with language name, optional proficiency label,
and an optional native-language flag — used by the Workday apply adapter.

## Encryption & read safety

The whole payload is **Fernet-encrypted before storage** (`core.crypto.encrypt`,
keyed by `CREDENTIALS_SECRET_KEY`); only `data_ciphertext` reaches the database.
The profile is PII, not a shared secret like a login cookie, so — unlike
[site credentials](credentials.md) — the decrypted profile **is returned to its
owner** so it can be reviewed and edited in the UI. It is never exposed to other
users (every route is scoped to `get_current_user`).

`ProfileRead` adds three fields on top of the stored data:

- `exists` — `false` when the user has never saved a profile (the API returns
  empty defaults rather than a 404), so the UI can tell an empty default apart
  from a deliberately-cleared profile.
- `updated_at` — when the profile was last saved.
- `resume_file` — metadata for an uploaded resume attachment, or `null`.

## Endpoints (prefix `/api/v1/profile`)

| Method | Path | Purpose                                            |
| ------ | ---- | -------------------------------------------------- |
| GET    | ``   | Get the profile (empty defaults if never saved)    |
| PUT    | ``   | Create or **fully replace** the profile text fields |
| PUT    | `/resume` | Upload or replace resume file (multipart `file`) |
| DELETE | `/resume` | Remove the resume file only                     |
| DELETE | ``   | Clear the profile (idempotent)                     |

`PUT` on the root path is a whole-profile replacement for text fields (not a partial
patch); the UI always sends the complete form. Uploading a resume does **not**
clear other fields, and saving text fields does **not** remove an uploaded resume.
All routes require auth and are scoped to the current user.

## Scope

This module owns encrypted storage, the profile API, and the Application profile
UI. Apply adapters and orchestration are documented in [appliers.md](appliers.md);
remaining gaps (e.g. LinkedIn resume PDF) are listed under
[roadmap.md → Phase 7 polish](../roadmap.md#phase-7-polish--remaining-gaps). See
[adr/0008-application-profile.md](../adr/0008-application-profile.md) for the
decision record.
