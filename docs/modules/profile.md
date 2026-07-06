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

Optional **LaTeX resume template** (`.tex` or `.zip` bundle, up to
`PROFILE_RESUME_TEMPLATE_MAX_BYTES` for a single file or
`PROFILE_RESUME_TEMPLATE_BUNDLE_MAX_BYTES` for a bundle, default 512 KB / 2 MB) is
stored encrypted alongside the profile. Upload via `PUT /profile/resume-template`;
metadata is returned on `GET /profile` as `resume_template` (`format`: `single` or
`bundle`, plus `entrypoint` and `file_count` for bundles). Placeholders use
`[[full_name]]`, `[[skills]]`, `[[experience]]`, `[[education]]`, `[[summary]]`,
`[[job_title]]`, `[[company]]`, and related contact fields. Substitution runs on
every `.tex` file in a bundle. `[[experience]]` is substituted verbatim because it
carries curated `\item`/`\textbf` list markup (the default template wraps it in an
`itemize`); every other placeholder is a free-text/PII scalar and is LaTeX-escaped
before substitution. Bundle archives must include `main.tex` or
`resume.tex` (or a single `.tex` file); allowed member types are `.tex`, `.sty`,
`.cls`, `.bib`, and common image formats. When no template is uploaded, a
built-in default template is used. Uploaded `.tex` / `.sty` / `.cls` members are
scanned for dangerous primitives (`\write18`, absolute/pipe/parent-path
`\input`/`\include`, `\openin`) at upload and again after placeholder
substitution (so verbatim `[[experience]]` markup cannot smuggle file-read
primitives into the compiler). `POST /jobs/{id}/generate-resume` curates placeholders (Pro
users: `resume_curation` AI purpose), renders LaTeX, and compiles a tailored PDF
(prefers `tectonic`, falls back to `pdflatex` with `-no-shell-escape` and a
minimal env that forces `openin_any=p` / `openout_any=p` / `shell_escape=f` so
host `texmf.cnf` defaults cannot re-enable shell escape or absolute-path reads).
The PDF persists in
`application_artifact` (per-user SHA-256 dedup, Fernet-encrypted). The response
includes `artifact_id` for preview/download via
`GET /application-artifacts/{id}/download`. On apply, pass `tailored_resume_artifact_id`
(or `tailored_resume_b64`) on `POST /jobs/{id}/apply` to attach the tailored PDF
instead of the static resume file.

`answers` is a free-form map of recurring application questions to the user's
canned response.

`work_experience` and `education` are structured lists used by apply adapters.
Work experience needs a job title, company, and start month/year; education rows
need at least a school name. Greenhouse also needs resolvable degree and field of
study catalog ids (or `default_degree_id` / `default_discipline_id` in source
config). Ashby uses these rows when `education_history_path` is configured;
Lever includes a formatted summary in `comments`.

`skills` is a list of skill names (up to 100 entries, 200 characters each).
`languages` is a structured list with language name, optional proficiency label,
and an optional native-language flag — used by the Workday apply adapter.
Greenhouse, Lever, and Ashby consume `skills` when their adapter config enables
structured profile mapping (see [appliers.md](appliers.md)).

## Encryption & read safety

The whole payload is **Fernet-encrypted before storage** (`core.crypto.encrypt`,
keyed by scrypt-stretched `CREDENTIALS_SECRET_KEY`); only `data_ciphertext`
reaches the database.
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
- `resume_template` — metadata for an uploaded LaTeX template, or `null`.

## Endpoints (prefix `/api/v1/profile`)

| Method | Path | Purpose                                            |
| ------ | ---- | -------------------------------------------------- |
| GET    | ``   | Get the profile (empty defaults if never saved)    |
| PUT    | ``   | Create or **fully replace** the profile text fields |
| PUT    | `/resume` | Upload or replace resume file (multipart `file`) |
| DELETE | `/resume` | Remove the resume file only                     |
| PUT    | `/resume-template` | Upload or replace LaTeX resume template (`.tex`) |
| DELETE | `/resume-template` | Remove the LaTeX template only           |
| DELETE | ``   | Clear the profile (idempotent)                     |

`PUT` on the root path is a whole-profile replacement for text fields (not a partial
patch); the UI always sends the complete form. Uploading a resume does **not**
clear other fields, and saving text fields does **not** remove an uploaded resume.
All routes require auth and are scoped to the current user.

## Scope

This module owns encrypted storage, the profile API, and the Application profile
UI. Apply adapters and orchestration are documented in [appliers.md](appliers.md).
See [adr/0008-application-profile.md](../adr/0008-application-profile.md) for the
decision record.
