# Module: Apply adapters

**Path:** `backend/app/appliers/`

Apply adapters submit (or preview) job applications for a single posting.
Each supported job site is one self-registering adapter, mirroring the scraper
and notifier registries. Orchestration lives in `ApplyService`
(`backend/app/services/apply.py`); the Jobs page **Apply** action calls
`POST /api/v1/jobs/{id}/apply` (preview via `dry_run: true`).

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

**Dry run:** `ApplyService.apply_to_job(..., dry_run=True)` (or
`ApplyContext.dry_run=True`) returns the JSON payload without calling Greenhouse.
Use this to preview applications before consent/audit UI ships.

**Live submit:** Greenhouse requires HTTP Basic auth with a per-board Job Board
API key (created in the employer's Greenhouse admin under API Credentials). Store
it in the source config or, preferably, in the linked [site
credential](credentials.md) as `session.job_board_api_key` so it stays encrypted.

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
| `gdpr_consent` | source/search config | When true, sets `consent.store` |
| `compliance_policy_id` | source/search config | Optional Lever compliance policy GUID |
| `silent_confirmations` | source/search config | When true, sets `silent` so Lever skips candidate email |
| `urls.<Label>` | profile `answers` | Extra profile URLs (e.g. `urls.Twitter`) |

**Dry run:** same as Greenhouse — preview JSON without calling Lever.

**Live submit:** requires a Postings API key (Super Admin → Integrations).
Store in source config or, preferably, credential `session.postings_api_key`.
Resume **files** are not uploaded in v1; `resume_text` is appended to
`comments` when present.

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

**Dry run:** same as Greenhouse — preview JSON without calling Ashby.

**Live submit:** requires an Ashby API key (Admin → Settings → API) with
`candidatesWrite`. Store in source config or, preferably, credential
`session.ashby_api_key`. System fields `_systemfield_name` and
`_systemfield_email` are always sent; resume **files** are not uploaded in v1.

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
| `CALYPSO_SESSION` | credential `cookies` | Authenticated candidate session cookie |
| `CALYPSO_CSRF_TOKEN` | credential `cookies` or `session.csrf_token` | CSRF token from the apply page |

**Dry run:** preview JSON (candidate contact fields + job posting id) without
calling Workday.

**Live submit:** requires cookies from a **logged-in** Workday candidate account
on the target tenant (create/sign-in on the apply page, then copy session cookies
from dev tools). The adapter creates the application, posts the legal name, and
calls finalize. Complex per-employer questionnaires, resume uploads, and
multi-page experience sections are **not** automated in v1 — finalize may fail
until those steps are completed manually or future adapter versions add them.
Resume **files** are not uploaded; `resume_text` is included in the preview
payload `comments` field only.

## Safety & consent

Live submission requires explicit opt-in per source (`source.auto_apply_enabled`,
default `false`). Toggle from the Sources page (only for adapters with a
registered applier). `ApplyService` rejects non–dry-run applies when opt-in is
off; preview (`dry_run`) still works.

**v1 limitations:** resume files are not uploaded; Workday questionnaires and
multi-page flows are not automated; Indeed/LinkedIn/generic sources have no
apply adapter. See [launch-checklist.md](../launch-checklist.md#7-auto-apply-optional--know-the-limits)
before advertising auto-apply on a public instance.

Every apply attempt (preview or live, success or failure) is recorded in
`application_log`. List recent rows via `GET /api/v1/application-logs`; the
Application profile page shows the same audit trail.

## Adding one

See [../recipes.md](../recipes.md) → "add a new apply adapter".
Tests must use saved fixtures and never hit the network.

## Error handling

`apply` returns `ApplyResult(status="failed", error=...)` for adapter-level
failures (missing config, HTTP errors). `ApplyService` raises `ValidationError`
for missing profile or unsupported adapter keys, and `NotFoundError` when the job
is out of scope.
