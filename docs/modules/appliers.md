# Module: Apply adapters

**Path:** `backend/app/appliers/`

Apply adapters submit (or preview) job applications for a single posting.
Each supported job site is one self-registering adapter, mirroring the scraper
and notifier registries. Orchestration lives in `ApplyService`
(`backend/app/services/apply.py`); the Jobs page **Apply** action calls
`POST /api/v1/jobs/{id}/apply` (preview via `dry_run: true`). Live submissions
are queued to Celery and polled via `GET /api/v1/application-logs/{id}`.

## Cover letter generation

Before submit, the Jobs apply dialog can draft a tailored cover letter via
`POST /api/v1/jobs/{id}/generate-cover-letter`. Generators live in
`backend/app/cover_letters/` (registry pattern matching summarizers). The offline
`heuristic` provider is available on every plan; Pro users use the effective
`SUMMARY_PROVIDER` (`openai`, `gemini`, `anthropic`, or `llamacpp` for local dev).
LLM failures fall back to heuristic. Env: `COVER_LETTERS_ENABLED`,
`COVER_LETTER_MAX_CHARS`, `COVER_LETTER_MAX_TOKENS` (see `.env.example`).

## Contract

```python
# app/appliers/types.py
class ApplyContext(BaseModel):
    job_external_id: str
    job_title: str
    company: str
    job_url: str
    config: dict          # merged source default_config + search config
    profile: ProfileData    # decrypted application profile (owner only)
    credentials: dict | None  # decrypted site credential payload, if any
    dry_run: bool = False   # when True, build payload but do not POST

class ApplyResult(BaseModel):
    status: str             # "submitted" | "dry_run" | "failed"
    error: str | None = None
    payload: dict | None = None
    external_application_id: str | None = None
```

```python
# app/appliers/base.py
class Applier(ABC):
    http: HttpClient
    @abstractmethod
    def apply(self, ctx: ApplyContext) -> ApplyResult: ...
```

## Registry

Adapters self-register with `@register_applier("key")`. The `key` matches a
source's `adapter_key` when that source supports auto-apply. Import the
`adapters` package to register built-ins; resolve with `get_applier(key)`.
`has_applier(key)` returns whether a source adapter can apply.

## Built-in adapters

| Key          | Strategy                         | Notes |
| ------------ | -------------------------------- | ----- |
| `greenhouse` | Job Board API JSON POST          | `POST boards-api.greenhouse.io/v1/boards/<token>/jobs/<id>`; see below |
| `lever`      | Postings API JSON POST           | `POST api.lever.co/v0/postings/<site>/<id>?key=...`; see below |
| `ashby`      | RPC `applicationForm.submit`     | `POST api.ashbyhq.com/applicationForm.submit`; see below |
| `workday`    | CXS apply flow (session cookies) | `POST …/jobpostings/<id>/jobapplications` then `…/name` + `…/finalize`; see below |
| `google_careers` | HiringCportal batchexecute RPC (session cookies) | `SaveCareersProfile` → `CreatePacket` → `SavePacket` → `SubmitPacket`; see below |
| `microsoft_careers` | Eightfold SmartApply JSON (session cookies) | `POST apply.careers.microsoft.com/api/application/v2/submit`; see below |
| `amazon_jobs` | amazon.jobs applicant JSON (session cookies) | `PUT /api/apply/applicant/` → draft → `submit_application`; see below |
| `apple_careers` | jobs.apple.com talent JSON (session cookies) | `PUT /api/v1/js/talent/<id>/applyJob` (+ resume upload); see below |
| `meta_careers` | metacareers.com Relay GraphQL (session cookies) | `POST /api/graphql/` (`xcp_create_application_v2`); see below |
| `indeed` | Viewjob parse + downstream ATS delegation | Fetches `/viewjob?jk=…`, delegates to Greenhouse/Lever/Ashby/Workday/Google when the listing embeds an employer apply URL; see below |
| `linkedin` | Guest job page + Voyager GraphQL + downstream ATS delegation | Fetches `/jobs-guest/jobs/api/jobPosting/{id}`, enriches offsite listings via Voyager when session cookies are present, delegates to Greenhouse/Lever/Ashby/Workday/Google/Microsoft/Amazon/Meta when the employer apply URL is recognized; see below |
| `snowflake_careers` | Delegates to Ashby | Snowflake's Phenom careers site uses Ashby for applications; delegates to the `ashby` adapter with `board=snowflake` |
| `shopify_careers` | Delegates to Ashby | Shopify's careers site uses Ashby for applications; delegates to the `ashby` adapter with `board=shopify` |
| `uber_careers` | Careers Fusion GraphQL | `POST /careers/apply/graphql` (`submitApplication`); screening questions via `getAdditionalQuestionsForJob`; see below |
| `smartrecruiters` | Application API JSON POST | `GET api.smartrecruiters.com/postings/<uuid>/configuration` then `POST …/candidates`; see below |

### Scrapers without apply adapters

These scraper keys have **no** registered applier — alerts and manual apply links
work, but the Jobs page **Apply** action is unavailable:

| Scraper key | Notes |
| ----------- | ----- |
| `playwright` / `generic_html` | Custom HTML sources; no generic apply path |

`GET /portals` sets `supports_auto_apply: false` for these keys. See
[roadmap.md → Phase 7 polish](../roadmap.md#phase-7-polish--shipped-follow-ups).

### Greenhouse

Maps `ProfileData` to the [Job Board application JSON
shape](https://developers.greenhouse.io/job-board.html#applications). Config /
credentials:

| Field | Where | Purpose |
| ----- | ----- | ------- |
| `board_token` | source `default_config` or parsed from `job_url` | Board slug (`boards.greenhouse.io/<token>/jobs/...`) |
| `job_board_api_key` | `default_config` or credential `session` | Employer Job Board API key for **live** submission |
| `gdpr_consent` | source/search config | When true, sets `data_compliance` consent flags |
| `question_<id>` | profile `answers` | Custom application questions (`question_5555`, etc.) |
| `skip_work_experience` | source/search config | When true, omit `employments` even when the profile has rows |
| `skip_education` | source/search config | When true, omit `educations` even when the profile has rows |
| `skip_education_lookup` | source/search config | When true, only numeric IDs and `education_id_aliases` resolve educations |
| `education_id_aliases` | source/search config | Map `school:<label>`, `degree:<label>`, or `discipline:<label>` to Greenhouse catalog ids |
| `default_degree_id` / `default_discipline_id` | source/search config | Fallback catalog ids when a profile row omits degree or field of study |

**Structured profile:** when the application profile has `work_experience`,
`education`, or `skills`, the adapter maps them to Greenhouse `employments` and
`educations` arrays. Work experience needs title, company, and start month/year.
Education rows need a resolvable `school_name_id`, `degree_id`, and
`discipline_id` (numeric profile values, `education_id_aliases`, or public List
Schools/Degrees/Disciplines lookup when `skip_education_lookup` is false).

**Dry run:** `ApplyService.apply_to_job(..., dry_run=True)` (or
`ApplyContext.dry_run=True`) returns the JSON payload without calling Greenhouse.
Use this to preview applications before consent/audit UI ships.

**Resume file:** when the application profile has an uploaded resume (see
[profile](profile.md)), live submit adds `resume_content` + `resume_content_filename`
to the JSON body. Plain `resume_text` is used only when no file is uploaded.

**Live submit:** Greenhouse requires HTTP Basic auth with a per-board Job Board
API key (created in the employer's Greenhouse admin under API Credentials). Store
it in the source config or, preferably, in the linked [site
credential](credentials.md) as `session.job_board_api_key` so it stays encrypted.
A 2xx response whose body reports an error (`success: false`, `error`, or
`errors`) is treated as a failed submit, not a success.

On success, `ApplyService` marks the `seen_job` status `applied`.

### Lever

Maps `ProfileData` to the [Postings apply JSON
shape](https://github.com/lever/postings-api#apply-to-a-job-posting). Config /
credentials:

| Field | Where | Purpose |
| ----- | ----- | ------- |
| `site` | source `default_config` or parsed from `job_url` | Board slug (`jobs.lever.co/<site>/...`) |
| `region` | source/search config | `"eu"` selects `api.eu.lever.co` |
| `postings_api_key` | `default_config` or credential `session` | Employer Postings API key for **live** submission |
| `gdpr_consent` | source/search config | When true, sets `consent` to `{"store": true, "marketing": false}` |
| `compliance_policy_id` | source/search config | Optional Lever compliance policy GUID. **Only applied when `gdpr_consent` is also set** — it rewrites `consent.store` to `{"provided": true, "compliancePolicyId": …}`; without `gdpr_consent` it is a no-op |
| `silent_confirmations` | source/search config | When true, sets `silent` so Lever skips candidate email |
| `urls.<Label>` | profile `answers` | Extra profile URLs (e.g. `urls.Twitter`) |
| `skip_structured_profile` | source/search config | When true, omit work history/education/skills from `comments` |

**Structured profile:** when the application profile has `work_experience`,
`education`, or `skills`, the adapter appends a formatted supplement to
`comments` (after the cover letter and optional `resume_text`). Lever's Postings
API has no native employment/education fields — use this for human-readable
context or configure custom questions via `answers`.

**Dry run:** same as Greenhouse — preview JSON without calling Lever.

**Live submit:** requires a Postings API key (Super Admin → Integrations).
Store in source config or, preferably, credential `session.postings_api_key`.
When the profile has an uploaded resume file, the adapter switches to
`multipart/form-data` with a `resume` part; otherwise `resume_text` is appended
to `comments` when present.

### Ashby

Maps `ProfileData` to the [`applicationForm.submit`
shape](https://developers.ashbyhq.com/reference/applicationformsubmit). Config /
credentials:

| Field | Where | Purpose |
| ----- | ----- | ------- |
| `board` | source `default_config` or parsed from `job_url` | Jobs page slug (`jobs.ashbyhq.com/<board>/...`) — informational for operators |
| `ashby_api_key` | `default_config` or credential `session` | Organization API key with `candidatesWrite` for **live** submission |
| `cover_letter_path` | source/search config | Optional form field path for cover letter + `resume_text` |
| `phone_path` | source/search config | Optional form field path for the profile phone |
| `location_path` | source/search config | Optional form field path for the profile location |
| `<form path>` | profile `answers` | Custom application questions (Ashby field `path` values) |
| `education_history_path` | source/search config | Ashby `EducationHistory` field path for profile `education` rows |
| `work_history_path` | source/search config | String field path for formatted profile `work_experience` |
| `skills_path` | source/search config | `MultiValueSelect` or String field path for profile `skills` |
| `skills_value_format` | source/search config | `"array"` (default) or `"string"` for `skills_path` |
| `allow_unpublished_job_posting` | source/search config | Opt-out flag: set **`false`** to send `allowSubmissionForUnpublishedJobPosting: false` and refuse submitting to unpublished postings. Omitted or truthy leaves the flag off, so Ashby's default (allowing unpublished submissions) applies |

**Structured profile:** when `education_history_path`, `work_history_path`, or
`skills_path` are set, the adapter maps profile `education`, `work_experience`,
and `skills` to Ashby field submissions. Education uses the Ashby
`EducationHistory` shape (`schoolName`, optional `degree`/`major`/dates).
Work history is sent as plain text; skills default to an array for
`MultiValueSelect` fields.

**Dry run:** same as Greenhouse — preview JSON without calling Ashby.

**Live submit:** requires an Ashby API key (Admin → Settings → API) with
`candidatesWrite`. Store in source config or, preferably, credential
`session.ashby_api_key`. System fields `_systemfield_name` and
`_systemfield_email` are always sent. When the profile has an uploaded resume,
live submit uses `multipart/form-data` with `_systemfield_resume` (override via
`config.resume_path`); otherwise `resume_text` may be appended to the
cover-letter field. The `allow_unpublished_job_posting: false` guard is carried
into the multipart form (as `"false"`) as well as the JSON body, so a resume
submit refuses unpublished postings just like a text-only submit.

### Uber Careers

Submits applications through Uber's Careers Fusion stack:

  POST `https://www.uber.com/careers/apply/api/getAdditionalQuestionsForJob`
  POST `https://www.uber.com/careers/apply/graphql` (`submitApplication`)

Config / credentials:

| Field | Where | Purpose |
| ----- | ----- | ------- |
| `locale` | source/search config | API locale code (default `en`) |
| `careers_locale_path` | source/search config | Careers URL prefix (default `us/en`) |
| `job_id` | source/search config | Optional numeric job id override |
| `session_token` / `sessionToken` | credential `session` | Logged-in Uber Careers session from `doSignIn` |
| `legal_right_to_work`, `in_usa`, `require_visa_sponsorship` | profile `answers` | EEO / eligibility fields (`Yes`/`No`) |
| `gender` / `sex`, `disability`, `veteran`, `race`, `sexual_orientation` | profile `answers` | Optional demographic fields when required |
| `uber_<question_id>` or `<formQuestionId>` | profile `answers` | Job-specific screening questions from `getAdditionalQuestionsForJob` |

**Structured profile:** maps `work_experience` to `positions` and `education` to
`educations` using Uber's month/year objects. Resume files attach as base64
`attachments` entries (`content` + `name`).

**Dry run:** fetches screening questions, builds the `applicationFormRequest`
preview (resume bytes redacted), and does not require a session token.

Only screening questions the API flags **required** gate live submit; optional
questions without a mapped answer are skipped rather than blocking the apply.

**Live submit:** requires the candidate's own Uber Careers session token.
Cover letters are not a first-class field on Uber's form — use screening-question
answers or the Application profile cover-letter generator before submit. Uber does
not expose a stable public employer API; this adapter reverse-engineers the same
Fusion GraphQL flow as the careers site.

### SmartRecruiters

Maps `ProfileData` to the [SmartRecruiters Application
API](https://developers.smartrecruiters.com/docs/application-api) candidate
shape. One adapter covers all SmartRecruiters-backed catalog employers (Atlassian,
Bosch, ServiceNow, etc.) — they share the same API. Config / credentials:

| Field | Where | Purpose |
| ----- | ----- | ------- |
| `company_id` | source `default_config` or parsed from `job_url` | Company slug (`jobs.smartrecruiters.com/<company_id>/...`) |
| `posting_uuid` | source/search config | Optional posting UUID override (else fetched from the public Postings detail API) |
| `smart_token` | `default_config` or credential `session` | Application API token (`X-SmartToken`) for **live** submission |
| `access_token` | `default_config` or credential `session` | OAuth bearer token alternative to `smart_token` |
| `gdpr_consent` | source/search config | Drives the consent decision. When the posting exposes consent settings, the adapter always sends `consentDecisions` (per-scope for a `SEPARATED` model, `{"SINGLE": …}` otherwise) — consent is granted by default and only withheld when `gdpr_consent` is explicitly `false`. With no posting consent settings, a truthy flag sends `consentDecisions` `{"SINGLE": true}` and an explicit `false` sends `{"SINGLE": false}`; unset sends no consent |
| `include_conditional_questions` | source/search config | When true, fetches conditional screening questions in configuration |
| `sr_<question_id>` | profile `answers` | Screening answers keyed by SmartRecruiters question id (also accepts raw id or `question_<id>`) |

**Dry run:** resolves the posting UUID via the public Postings detail API,
builds the candidate JSON, and — when an Application API token is present in
credentials — fetches screening questions and reports any missing required
answers in the preview payload.

**Live submit:** requires a SmartRecruiters Application API token or OAuth
bearer token with `candidate_applications_manage` scope. Store in source config
or, preferably, credential `session.smart_token` / `session.access_token`.
Resume files are sent as base64 in the `resume` object; cover letters use
`messageToHiringManager`. Required screening questions must be mapped in
`profile.answers` before live submit succeeds.

### Workday

Maps `ProfileData` to the Workday CXS apply flow used by `*.myworkdayjobs.com`
career sites. Config / credentials:

| Field | Where | Purpose |
| ----- | ----- | ------- |
| `tenant` | source `default_config` or parsed from `job_url` | Workday tenant slug |
| `site` | source `default_config` or parsed from `job_url` | Board/site path segment |
| `region` | source/search config | Optional cluster host (`wd5`, `wd12`, …) |
| `locale` | source/search config | Locale prefix (default `en-US`) |
| `country_id` | source/search config | Country WID for name fields (default `US`) |
| `job_path` | source/search config | Optional override when `job_url` is missing |
| `questionnaire_id` | source/search config | Override primary questionnaire WID (else from job posting CXS detail) |
| `secondary_questionnaire_id` | source/search config | Override secondary questionnaire WID |
| `supplementary_questionnaire_id` | source/search config | Override supplementary questionnaire WID |
| `questionnaire_answers` | source/search config | Optional alias map `{questionId: value}` merged with profile `answers` |
| `skip_questionnaires` | source/search config | When true, skip all questionnaire submission |
| `skip_primary_questionnaire` / `skip_secondary_questionnaire` / `skip_supplementary_questionnaire` | source/search config | Skip one questionnaire type |
| `auto_terms_consent` | source/search config | When true, PUT `termsandconditions` with `acceptTermsAndAgreements: true` before finalize |
| `skip_resume_upload` | source/search config | When true, skip CXS resume upload even when the profile has a stored file |
| `skip_work_experience` | source/search config | When true, skip CXS work-experience rows even when the profile has them |
| `skip_education` | source/search config | When true, skip CXS education rows even when the profile has them |
| `skip_education_lookup` | source/search config | When true, send descriptor-only degree/field values without tenant catalog lookup |
| `education_lookup_aliases` | source/search config | Optional map of `degree:<label>` / `fieldOfStudy:<label>` to catalog WIDs |
| `skip_skill_lookup` | source/search config | When true, send descriptor-only skill names without tenant catalog lookup |
| `skill_lookup_aliases` | source/search config | Optional map of skill label to catalog WID |
| `skip_skills` | source/search config | When true, skip CXS skill rows even when the profile has them |
| `skip_languages` | source/search config | When true, skip CXS language rows even when the profile has them |
| `CALYPSO_SESSION` | credential `cookies` | Authenticated candidate session cookie |
| `CALYPSO_CSRF_TOKEN` | credential `cookies` or `session.csrf_token` | CSRF token from the apply page |

**Dry run:** preview JSON (candidate contact fields + job posting id) without
calling Workday. When the profile has an uploaded resume, the preview includes a
`resumeAttachments` section with filename, size, and content type (no file bytes).

**Live submit:** requires cookies from a **logged-in** Workday candidate account
on the target tenant (create/sign-in on the apply page, then copy session cookies
from dev tools). The adapter creates the application, posts the legal name, uploads
the resume file to the CXS `attachments` endpoint and registers it on
`resumeattachments` (when the application profile has a stored file), submits
mapped **primary / secondary / supplementary questionnaires** (when the job
posting exposes them), optionally accepts terms (`auto_terms_consent`), and calls
finalize. Question answers come from `profile.answers` (question WID or label →
answer WID or label such as `Yes` / `No`). Use **dry run** to preview
`questionnaireAnswers` and `resumeAttachments` before enabling live apply.

Set `skip_resume_upload: true` in source/search config to omit the resume upload
steps while still applying other sections.

**Work experience / education:** when the application profile has structured
`work_experience` or `education` rows, the adapter POSTs each applicable row to
`jobapplication/{id}/workexperiences` and `jobapplication/{id}/educations`
before questionnaires and finalize. Work experience needs title, company, and
start month/year; education needs at least a school name. Degree and field of
study are resolved against tenant catalogs via
`GET …/institutionvalues/degree?searchText=…` and
`GET …/institutionvalues/fieldOfStudy?searchText=…` when session cookies are
available (exact → normalized → fuzzy match, then descriptor fallback). Paste a
catalog WID directly into the profile degree/field fields or set
`education_lookup_aliases` to override a label. Use dry run to preview resolved
`id` values before live apply. Set `skip_education_lookup` to force
descriptor-only payloads. Set `skip_work_experience` or `skip_education` to omit
either section.

**Skills / languages:** when the application profile has `skills` or structured
`languages` rows, the adapter POSTs each applicable entry to
`jobapplication/{id}/skills` and `jobapplication/{id}/languages` after
experience/education and before questionnaires. Skills are resolved against the
tenant catalog via `GET …/institutionvalues/skill?searchText=…` when session
cookies are available (exact → normalized → fuzzy match, then descriptor
fallback). Paste a catalog WID directly into the profile skill name or set
`skill_lookup_aliases` to override a label. Languages support optional
proficiency and a native-language flag. Use dry run to preview `skills` /
`languages` payloads. Set `skip_skills`, `skip_skill_lookup`, or
`skip_languages` to omit or bypass lookup for either section.

**Questionnaires:** Workday exposes `questionnaireId` fields on the public job
detail CXS response. The adapter fetches each questionnaire definition, maps
`profile.answers` to `questionnaireAnswers`, and POSTs
`jobapplication/{id}/questionnaireresponse?type=primary|secondary|supplementary`.
Required questions without a mapped answer — or with a present value that cannot
be converted (unmatched choice label, non-int / non-positive numeric) — fail
before finalize with a clear error listing the question ids.

**Still manual / best-effort:** websites, and complex
branching questionnaires where follow-up questions depend on earlier choices you
did not map. LinkedIn/generic sources have no apply adapter. Branching
questionnaires only submit answers you explicitly map in `profile.answers`. See
[launch-checklist.md](../launch-checklist.md#7-auto-apply-optional--know-the-limits)
before advertising auto-apply on a public instance.

### Google Careers

Google Careers has no employer-issued API. The adapter maps `ProfileData` to a
Google **Careers Profile** and (on live submit) calls the authenticated
`HiringCportalFrontendUi` batchexecute RPC sequence:

1. `SaveCareersProfile` (`qvYBjf`)
2. `CreatePacket` (`tBY1Qe`)
3. `SavePacket` (`o6YK3`)
4. `SubmitPacket` (`pmtdJd`)

Config / credentials:

| Field | Where | Purpose |
| ----- | ----- | ------- |
| `apply_job_id` | source/search config (optional) | Opaque apply token from the job's sign-in URL (`jobId=…`). Fetched automatically from the job detail page when omitted. |
| `location_code` | source/search config | Two-letter country code (`loc` query param) when `apply_job_id` is set manually |
| `company_resource` | source/search config | `gweb-careers-proto/…/companies/…` path when known |
| `resume_upload_url` | source/search config | Optional override for Scotty resume upload endpoint (defaults to Google's `/about/careers/attachmentupload/upload`) |
| Google account cookies | credential `cookies` | Logged-in session (`SID`, `SAPISID`, `__Secure-1PSID`, …) |
| `at` / `csrf_token` | credential `session` | CSRF token (`SNlM0e`) from an authenticated apply page |

**Dry run:** fetches the public job detail page (`ds:0` embedded JSON), resolves
the apply token and `apply_url`, and returns the mapped Careers profile plus the
RPC steps that would run. No Google login required.

**Live submit:** requires the user's own Google account cookies and CSRF token.
When the application profile has an uploaded resume file, the adapter uploads it
via Google's Scotty resumable attachment endpoint (`/about/careers/attachmentupload/upload`)
before the batchexecute sequence and attaches the returned reference on the Careers
profile (`resumeAttachment`). Override the upload URL with `resume_upload_url` in
source/search config if Google changes the endpoint. Employer-specific screening
questions may need explicit `profile.answers` mappings. RPC ids can change when
Google redeploys the careers frontend; verify in DevTools if live submit starts
failing after a Google UI update.

**Limits:** Google enforces application rate limits in the UI (e.g. three jobs
per 30 days). Treat live auto-apply as best-effort; always preview with dry run
first.

### Microsoft Careers

Microsoft's external careers portal (`apply.careers.microsoft.com`) is powered by
Eightfold SmartApply. The adapter uses the public JSON endpoints exposed to the
apply UI:

| Step | Endpoint |
| ---- | -------- |
| Job detail | `GET /api/apply/v2/jobs/<id>?domain=<domain>&hl=en` |
| Questions | `GET /api/apply/v2/questions?domain=<domain>&position_id=<id>` |
| Candidate profile | `POST /api/apply/v2/candidate` |
| Resume upload | `POST /api/pcsx/upload_resume` (base64 `resume_content`) |
| Submit | `POST /api/application/v2/submit` (`pids` = position id string) |

Config / credentials:

| Field | Where | Purpose |
| ----- | ----- | ------- |
| `domain` | source `default_config` | Eightfold domain slug (default `microsoft.com`) |
| `position_id` | source/search config | Optional override when `job_url` / `external_id` are ambiguous |
| `hl` / `locale` | source/search config | Locale query param (default `en`) |
| Microsoft Careers cookies | credential `cookies` | Logged-in candidate session from `apply.careers.microsoft.com` |
| `csrf_token` | credential `session` | Optional `X-CSRF-Token` (fetched from the apply page when omitted) |
| `questionId` keys | profile `answers` | Employer screening questions (country-specific sections are best-effort) |

**Dry run:** fetches job detail and questionnaire metadata, then returns the
mapped candidate plus the submit body (`domain`, `pids`, `candidate`, `answers`).
No Microsoft login required. Submitted `answers` are driven by the fetched
questionnaire: only `profile.answers` whose key matches a `questionId` in the
questions payload are sent, so unrelated answer keys are never leaked to Microsoft.

**Live submit:** requires the candidate's own logged-in Microsoft Careers session
cookies. Resume files upload via `/api/pcsx/upload_resume` before submit. Complex
country-specific questionnaires (e.g. EEO, consent) may need explicit
`profile.answers` mappings. Always preview with dry run first.

### Amazon Jobs

Amazon's external careers portal (`www.amazon.jobs` / `account.amazon.jobs`) uses
authenticated applicant JSON endpoints:

| Step | Endpoint |
| ---- | -------- |
| Job lookup (public) | `GET /<locale>/search.json?result_limit=1&base_query=<id_icims>` |
| Applicant profile | `PUT /api/apply/applicant/` |
| Resume upload | `POST /api/apply/documents` (multipart `file`) |
| Draft application | `POST /api/apply/jobs/<id>/application/draft_application` |
| Submit | `POST /api/apply/jobs/<id>/application/submit_application` |

Config / credentials:

| Field | Where | Purpose |
| ----- | ----- | ------- |
| `locale` | source/search config | Path locale for search.json (default `en`) |
| `job_id` / `id_icims` | source/search config | Optional override when `job_url` / `external_id` are ambiguous |
| `recruiting_source` | source/search config | Optional tag passed when creating the draft application |
| amazon.jobs cookies | credential `cookies` | Logged-in candidate session from `www.amazon.jobs` or `account.amazon.jobs` |

**Dry run:** loads the posting from public `search.json`, then returns the mapped
applicant body plus the draft/submit endpoint URLs. No Amazon login required.

**Live submit:** requires the candidate's own logged-in amazon.jobs session
cookies. Resume files upload via `/api/apply/documents` before submit.
Employer-specific screening questions may need explicit `profile.answers`
mappings. Amazon may enforce application limits and CAPTCHA on the apply portal;
treat live auto-apply as best-effort and always preview with dry run first.

### Apple Careers

Apple's careers portal (`jobs.apple.com`) uses authenticated talent JSON
endpoints behind the apply UI:

| Step | Endpoint |
| ---- | -------- |
| Job detail (public) | Server-rendered `/en-us/details/<reqId>/<slug>` hydration JSON |
| Questionnaire | `GET /api/v1/js/jobDetails/<positionId>/questionnaire` |
| Resume upload | `POST /api/v1/js/talent/<talentId>/file/uploadFile` |
| Submit | `PUT /api/v1/js/talent/<talentId>/applyJob` |

Config / credentials:

| Field | Where | Purpose |
| ----- | ----- | ------- |
| `locale` | source/search config | Path locale (default `en-us`) |
| `post_locations` / `store_locations` | source/search config | Location objects for retail roles that require store selection |
| Apple Careers cookies | credential `cookies` | Logged-in candidate session from `jobs.apple.com` |
| `talent_id` | credential `session` | Apple talent id (`talentId` from the signed-in profile) |
| `csrf_token` | credential `session` | `X-Apple-CSRF-Token` (from `GET /api/v1/js/CSRFToken`) |
| Questionnaire keys | profile `answers` | Employer screening questions (best-effort) |

**Dry run:** fetches the public job detail page, parses embedded hydration JSON,
and returns the mapped `talent` + `roles` body that would be sent to `applyJob`.
No Apple login required.

**Live submit:** requires the candidate's own logged-in Apple Careers session
cookies, `talent_id`, and CSRF token. Resume files upload via
`/file/uploadFile` before submit. Retail **PIPE** roles with
`role_location_selection` need explicit `store_locations` / `post_locations` in
source config. Treat live auto-apply as best-effort; always preview with dry run
first.

### Meta Careers

Meta's candidate portal (`metacareers.com`) uses Relay GraphQL for job detail
and application submission:

| Step | Operation |
| ---- | --------- |
| Job detail (public) | `CandidatePortalJobDetailsViewQuery` on `/api/graphql/` |
| Apply entry | `/profile/create_application/<requisition_id>/` |
| Submit | `CandidateChatbotApplicationDetailSubmitMutation` → `xcp_create_application_v2` |

Config / credentials:

| Field | Where | Purpose |
| ----- | ----- | ------- |
| `requisition_id` | source/search config or parsed from job URL | Numeric Meta requisition id |
| Meta Careers cookies | credential `cookies` | Logged-in candidate session from `metacareers.com` |
| `session_id` | credential `session` | Browser session key from the apply flow |
| `lsd` / `csrf_token` | credential `session` | Optional anti-CSRF token (otherwise fetched from the apply page) |
| EEO / screening keys | profile `answers` | Voluntary self-ID and employer questions (best-effort) |

**Dry run:** loads public job metadata via `CandidatePortalJobDetailsViewQuery`
and returns the mapped application state that would be posted to
`xcp_create_application_v2`. No Meta login required.

**Live submit:** requires the candidate's own logged-in Meta Careers session
cookies and `session_id`. Resume files upload via Relay multipart on the submit
mutation. Meta's AI-assisted application flow may require additional
`profile.answers` mappings for employer-specific questionnaires. Treat live
auto-apply as best-effort; always preview with dry run first.

### Indeed

Indeed listings rarely submit on Indeed itself — most **Easily apply** jobs
redirect to an employer ATS. The adapter fetches the public viewjob page,
parses embedded `window._initialData`, and **delegates** to Greenhouse, Lever,
Ashby, Workday, Google Careers, Microsoft Careers, Amazon Jobs, or Meta Careers when the
downstream apply URL is recognized.
Config / credentials:

| Field | Where | Purpose |
| ----- | ----- | ------- |
| `host` | source/search config | Indeed hostname when building `/viewjob?jk=…` (default `www.indeed.com`) |
| `external_apply_url` | source/search config | Optional override to skip the viewjob fetch (pin a known employer apply URL) |
| Indeed session cookies | credential `cookies` | Logged-in Indeed account (`PPID`, `SOCK`, …) for **Indeed-hosted** Easy Apply live submit |
| `csrf_token` | credential `session` | Optional `X-Indeed-Csrf-Token` for smartapply live submit |

**Dry run:** fetches viewjob (unless `external_apply_url` is set), resolves the
apply route, and previews either the delegated ATS payload or the Indeed-hosted
smartapply contact payload. No Indeed login required for delegation previews.

**Live submit (delegated):** uses the downstream adapter's requirements (API
keys, Workday cookies, etc.) — the preview payload includes `indeed_route` and
`delegated_adapter` metadata.

**Live submit (Indeed-hosted):** when the listing has no external ATS URL but
does expose an Easy Apply button, posts to
`smartapply.indeed.com/beta/indeedapply/v2/applications` with the user's Indeed
session cookies. When the application profile has an uploaded resume file, live
submit includes `applicant.resume.file` (`fileName`, `contentType`, Base64
`data`) per the Indeed Apply payload shape; plain `resumeText` is used only when
no file is stored. Multi-step employer questionnaires are best-effort; map answers
in `profile.answers`. Cloudflare may block unauthenticated viewjob fetches —
reuse [site credentials](credentials.md) session cookies from scraping.

**Unsupported:** external apply URLs that are not a recognized ATS (e.g. custom
career sites, Breezy).

### LinkedIn

LinkedIn listings either expose **Easy Apply** on LinkedIn itself or redirect to
an employer ATS. The adapter fetches the public guest job-posting page, optionally
enriches offsite listings via authenticated Voyager GraphQL (`companyApplyUrl`),
and **delegates** to Greenhouse, Lever, Ashby, Workday, Google Careers, Microsoft
Careers, Amazon Jobs, or Meta Careers when the downstream apply URL is recognized.

Config / credentials:

| Field | Where | Purpose |
| ----- | ----- | ------- |
| `external_apply_url` | source/search config | Optional override to skip the guest page fetch (pin a known employer apply URL) |
| `li_at` + `JSESSIONID` | credential `cookies` | Logged-in LinkedIn account for Voyager enrichment and **LinkedIn-hosted** Easy Apply live submit |
| `csrf_token` | credential `session` | Optional CSRF token for Voyager requests (defaults to the `JSESSIONID` cookie value) |

**Dry run:** fetches the guest job-posting page (unless `external_apply_url` is
set), resolves the apply route, and previews either the delegated ATS payload or
the LinkedIn Easy Apply contact payload. Voyager enrichment for offsite listings
requires session cookies but is not required for Easy Apply previews detected from
the guest HTML.

**Live submit (delegated):** uses the downstream adapter's requirements (API
keys, Workday cookies, etc.) — the preview payload includes `linkedin_route` and
`delegated_adapter` metadata.

**Live submit (LinkedIn-hosted Easy Apply):** when the listing exposes an Easy
Apply button, loads the application form via Voyager GraphQL and posts to
`/voyager/api/voyagerJobsDashOnsiteApplyApplication?action=submitApplication`
with the user's LinkedIn session cookies. When the application profile has an
uploaded resume file and the form includes a document-upload field, live submit
registers the file via `voyagerMediaUploadMetadata`, uploads it to LinkedIn's
Ambry endpoint, and includes the asset URN in `fileUploadResponses`. Plain
`resume_text` remains a preview/fallback when no file is stored. Multi-step
employer questionnaires are best-effort; map answers in `profile.answers` using
the form element URN or a normalized field label key.

**Unsupported:** external apply URLs that are not a recognized ATS when Voyager
enrichment cannot resolve them (add session cookies or `external_apply_url`).
Auth-walled guest pages need [site credentials](credentials.md) session cookies
from scraping.

## Safety & consent

Live submission requires explicit opt-in per source (`source.auto_apply_enabled`,
default `false`). Toggle from the Sources page (only for adapters with a
registered applier). `ApplyService` rejects non–dry-run applies when opt-in is
off; preview (`dry_run`) still works. Enabling auto-apply is the user's consent
to transmit application-profile PII to that employer's career site; the privacy
policy discloses the data categories and lawful basis (consent for opt-in
third-party sends).

Every apply attempt (preview or live, success or failure) is recorded in
`application_log` with baseline tracking metadata (`employer_domain`, `posting`
fields) for inbox triage, plus a `user_consent` stamp (`basis`, `mechanism`,
`live_submission`, `recorded_at`) so each submission has an auditable HeadStart
opt-in artifact. Queue-time consent is preserved when a queued log is updated
with the final outcome. List recent rows via `GET /api/v1/application-logs`; fetch one
queued row via `GET /api/v1/application-logs/{id}` while a live submit runs in
the worker. At most one in-flight live apply (`queued` or `processing`) per job
is allowed — enforced by a partial unique index so concurrent enqueue requests
cannot double-submit. The worker commits the `queued` → `processing` lease
before the employer POST so `acks_late` redelivery cannot double-submit
(NTF-03). Successful live applies set `seen_job.applied_at`. When
`source.auto_apply_enabled` is on, the scrape pipeline queues applies for new
matches automatically (same Celery path as the Jobs page **Apply** button), up
to the plan's rolling 24-hour live-apply volume cap (`max_auto_applies_per_day`
in `app/core/plans.py` — Free 3 / Starter 5 / Plus 10 / Pro 20). Further
pipeline matches are skipped silently until the window has capacity; manual
**Apply** from the Jobs page is unchanged. Dry-run previews do not count toward
the cap. The Application profile page shows the same audit trail.

**v1 limitations:** Workday degree/field and skill lookup is best-effort and needs
authenticated session cookies; unmatched labels still fall back to descriptors.
Google Careers live submit needs the candidate's own Google account session and
CSRF token; resume upload and employer questionnaires are best-effort. Microsoft
Careers live submit needs the candidate's own logged-in session on
`apply.careers.microsoft.com`; country-specific screening questions are
best-effort. Branching questionnaires only
submit answers you explicitly map in `profile.answers`. Uber Careers live submit
needs a logged-in careers session token; employer questionnaires map via
`profile.answers`. See
[launch-checklist.md](../launch-checklist.md#7-auto-apply-optional--know-the-limits)
before advertising auto-apply on a public instance.

## Adding one

See [../recipes.md](../recipes.md) → "add a new apply adapter".
Tests must use saved fixtures and never hit the network.

## Error handling

`apply` returns `ApplyResult(status="failed", error=...)` for adapter-level
failures (missing config, HTTP errors). `ApplyService` raises `ValidationError`
for missing profile or unsupported adapter keys, and `NotFoundError` when the job
is out of scope.
