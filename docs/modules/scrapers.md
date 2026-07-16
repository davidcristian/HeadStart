# Module: Scrapers

**Path:** `backend/app/scrapers/`

Scrapers fetch postings from a job site and normalize them into `JobPosting`s.
Each site is one self-registering adapter. This is the primary extension point.

## Contract

```python
# app/scrapers/types.py
class JobPosting(BaseModel):
    external_id: str      # stable id from the site; used for dedup
    title: str
    company: str
    location: str = ""
    url: str              # http(s) only; non-http schemes cleared at ingest (NTF-08)
    posted_at: datetime | None = None
    raw: dict = {}        # original payload, for debugging

class ScrapeContext(BaseModel):
    query_url: str        # the search URL/endpoint configured by the user
    filters: dict         # arbitrary filters from the search
    config: dict          # merged source default_config + search config
```

`JobPosting.url` is validated on construct: empty stays empty; only absolute
`http`/`https` URLs with a host are kept (`safe_http_job_url` in
`app/scrapers/url.py`). Non-http schemes (`javascript:`, `data:`, relative
paths) are cleared to `""` so notifiers never emit poisoned Apply / click
links from a hostile scraper payload.

```python
# app/scrapers/base.py
class Scraper(ABC):
    http: HttpClient                       # injected sync HTTP helper (httpx.Client)
    @abstractmethod
    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]: ...
```

## Registry

Adapters self-register with `@register_scraper("key")`. The `key` matches a
source's `adapter_key`. All adapter modules are imported in
`app/scrapers/adapters/__init__.py`, so importing the package registers
everything. The worker resolves a scraper with `get_scraper(adapter_key)`.

## Built-in adapters

| Key             | Strategy                                  | Notes                                  |
| --------------- | ----------------------------------------- | -------------------------------------- |
| `greenhouse`    | Public Greenhouse job board JSON API      | `boards-api.greenhouse.io/v1/boards/<token>/jobs` |
| `lever`         | Public Lever Postings API                 | `api.lever.co/v0/postings/<site>?mode=json`; also accepts `jobs.lever.co/<site>` URLs |
| `ashby`         | Public Ashby Postings API                 | `api.ashbyhq.com/posting-api/job-board/<board>`; also accepts `jobs.ashbyhq.com/<board>` URLs. `/sources/detect` accepts the jobs host or an `*.ashbyhq.com` host whose path contains `posting-api/job-board` (not arbitrary hosts with that path substring) |
| `smartrecruiters` | Public SmartRecruiters Postings API     | `api.smartrecruiters.com/v1/companies/<company_id>/postings`; also accepts `careers.smartrecruiters.com/<company_id>` URLs. Apply via Application API — see [appliers.md](appliers.md) |
| `workday`       | Public Workday CXS jobs API (POST)        | `*.myworkdayjobs.com/wday/cxs/<tenant>/<site>/jobs`; also accepts careers board URLs |
| `google_careers`| Embedded search JSON in HTML              | `google.com/about/careers/applications/jobs/results?...`; parses `AF_initDataCallback` `ds:1`; also accepts `careers.google.com` |
| `microsoft_careers` | Eightfold PCSX JSON search API       | `apply.careers.microsoft.com/api/pcsx/search`; config `domain` (default `microsoft.com`) + optional `q` / `location`; also accepts careers board URLs. `/sources/detect` requires host `careers.microsoft.com` or a `*.careers.microsoft.com` suffix (dot boundary — not `evilcareers.microsoft.com`) |
| `meta_careers`      | Relay GraphQL search (form POST)       | `metacareers.com/graphql` with `CareersJobSearchResultsDataQuery`; config `q` + optional `graphql_doc_id`; also accepts `metacareers.com/jobsearch` URLs |
| `amazon_jobs`   | Public search JSON API                    | `amazon.jobs/<locale>/search.json`; config `locale` (default `en`) + optional `base_query` / `loc_query` / `country`; also accepts search board URLs |
| `apple_careers` | Embedded search JSON in HTML              | `jobs.apple.com/<locale>/search?...`; parses `window.__staticRouterHydrationData`; config `locale` (default `en-us`) + optional `search` / `location`; also accepts careers search URLs |
| `shopify_careers` | Embedded React Router flight stream in HTML | `shopify.com/careers`; parses `window.__reactRouterContext.streamController.enqueue` loader data (Ashby-backed, no public Postings API); config optional `q` / `company` / `max_results` (no `board` — that key is Snowflake/Ashby-only) |
| `uber_careers` | Public `loadSearchJobsResults` JSON API | `uber.com/.../careers/list`; `POST /api/loadSearchJobsResults?localeCode=en`; config optional `q` (client-side), `country` (server-side location filter), `careers_locale_path` (default `us/en`) |
| `snowflake_careers` | Public Ashby Postings API (Ashby-backed) | `careers.snowflake.com`; `GET api.ashbyhq.com/posting-api/job-board/snowflake`; config optional `q` (client-side), `board` (default `snowflake`), `include_compensation` |
| `indeed`        | Embedded search JSON in HTML (selectolax fallback) | `*.indeed.com/jobs?...`; parses `mosaic-provider-jobcards`; may need [credentials](credentials.md) for Cloudflare — **ToS risk** when session cookies are used (see [Safety](#linkedin--indeed-credentialed-scrape-tos-risk-xct-19)) |
| `linkedin`      | Guest search pagination API (HTML fragments) | Opt-in only (not URL-detected). `linkedin.com/jobs/search?...` → guest `seeMoreJobPostings/search`; may need [credentials](credentials.md) for auth walls — **ToS risk** when session cookies are used (see [Safety](#linkedin--indeed-credentialed-scrape-tos-risk-xct-19)) |
| `generic_html`  | CSS selectors from config (selectolax)    | For simple static pages; configured in the UI |
| `playwright`    | Headless browser (base helper)            | For JS-heavy/anti-bot pages (opt-in)   |

> Prefer a site's JSON/search endpoint over HTML scraping. Reach for
> `playwright` only when necessary.

## Adding one

See [../recipes.md](../recipes.md) → "add a new job-site scraper".
Tests must use saved fixtures and never hit the network. Also add the adapter
key to `FREE_SCRAPERS` or `PREMIUM_SCRAPERS` in `app/core/plans.py` — unclassified
keys are denied on every plan.

## Error handling

`fetch` may raise; the worker catches, logs, and records the failure against the
search without crashing. Be a polite client: real User-Agent, respect intervals,
no retry storms.

Upstream JSON/HTML is **untrusted**: a single bad field or record must not abort
the run. Parse defensively — a malformed date becomes `None` (use
`app.scrapers.dates.parse_iso8601` for ISO strings, or
`parse_epoch_seconds` / `parse_epoch_millis` for Unix epochs — both catch
`OverflowError`/`OSError`/`ValueError` from `fromtimestamp`), a non-list/non-dict
payload node is skipped, and a non-finite or out-of-range count/index falls back
to a safe default rather than raising (use `app.scrapers.numbers.coerce_count`
for `total` / `hits` / `count` / `totalFound` / `totalRecords` — bare `int()`
raises on JSON `Infinity`/`NaN`). Shopify Careers' React Router flight-stream
resolver (`_resolve_node`) also caps reference-graph depth (default 64) so a long
non-cyclic chain cannot raise `RecursionError`. Aborting is reserved for a
payload that isn't recognizable at all (e.g. the expected top-level
array/object is missing).

### HTML parsing (selectolax)

Adapters that parse HTML (`generic_html`, Indeed fallback, LinkedIn guest
fragments) use **selectolax** (Modest/lolhtml C extension). That dependency is
declared as `selectolax>=0.4.10` in `backend/pyproject.toml` and pinned with
hashes in the pip-tools lockfiles (`backend/requirements*.txt`; see
[ADR-0012](../adr/0012-backend-dependency-lockfiles.md)). Do not raise the floor
or bump the lock without reviewing the release notes — this code path ingests
attacker-influenced markup.

**Upstream health / fallback.** If selectolax stalls, ships an unpatched parser
CVE, or a release looks untrustworthy, pin (or roll back) via `just lock-backend`
and treat **lxml** (`lxml.html`) as the drop-in CSS-selector fallback for
`generic_html` / Indeed HTML parsing. LinkedIn fragment parsing would follow the
same swap. Prefer keeping one HTML library; do not add lxml alongside selectolax
unless the pin is blocked.

Outbound HTTP from scrapers is restricted to public `http`/`https` destinations.
Private, loopback, link-local, and cloud-metadata addresses are rejected in the
shared `HttpClient` (including redirect targets) and on every Playwright request
(including redirects). DNS is resolved once and the connect uses that IP (Host +
TLS SNI keep the original hostname) so a rebinding resolver cannot slip a private
address past the check. See `app.core.outbound_url` / `app.core.outbound_http`.
Playwright pages use `ignore_https_errors` because the pinned connect is an IP
literal while certificate SANs name the hostname.

Response bodies are streamed and capped (default **5 MiB**, override with
`SCRAPER_MAX_RESPONSE_BYTES` / `HttpClient(max_response_bytes=…)`). An oversized
`Content-Length` is rejected before the body is read; chunked responses that
cross the cap raise `ResponseTooLargeError` mid-stream so a hostile `query_url`
cannot OOM a shared worker.

## Rate limiting

Each adapter has a default minimum gap between outbound HTTP requests during one
scrape. Override per source (or search) via `default_config` / `config`:

```json
{ "rate_limit_min_interval_seconds": 2.5 }
```

Set to `0` to disable throttling for that source. Resolution order: merged
config value → adapter default → no limit.

| Adapter        | Default interval (s) |
| -------------- | -------------------- |
| `greenhouse`   | 1.0                  |
| `lever`        | 1.0                  |
| `ashby`        | 1.0                  |
| `smartrecruiters` | 1.0               |
| `workday`      | 2.5                  |
| `google_careers` | 2.5                |
| `meta_careers` | 3.0                  |
| `microsoft_careers` | 2.5             |
| `amazon_jobs`  | 2.5                  |
| `apple_careers` | 3.0                 |
| `shopify_careers` | 3.0               |
| `snowflake_careers` | 1.0             |
| `uber_careers` | 2.5                  |
| `indeed`       | 5.0                  |
| `linkedin`     | 7.5                  |
| `generic_html` | 2.0                  |
| `playwright`   | 5.0                  |

Limits are enforced in the shared `HttpClient` (for multi-request scrapers), via
a per-page Playwright route guard (all navigations and subresource fetches), and
at the start of a `playwright` fetch. Limits are per scrape run, not global
across workers.

## Playwright adapter (production)

The `playwright` adapter is optional locally (`pip install -e ".[playwright]"`)
and **enabled in production on the worker only**:

- **Docker:** `backend/Dockerfile` target `worker` installs Chromium; the lean
  `api` / `beat` images omit Playwright. Runtime stays as `appuser`; Chromium
  keeps its process sandbox (no `--no-sandbox` unless `PLAYWRIGHT_NO_SANDBOX`
  in local/test — OPS-27).
- **Browser pool:** each Celery worker child process reuses one headless Chromium
  instance across scrapes (`app/scrapers/playwright_browser.py`). The browser
  is closed on worker shutdown. Launch args keep `--disable-dev-shm-usage` /
  `--disable-gpu` for containers without disabling the sandbox.
- **Timeouts / retries:** env vars `PLAYWRIGHT_NAVIGATION_TIMEOUT_MS` (default
  `30000`) and `PLAYWRIGHT_MAX_RETRIES` (default `1`). Per-source overrides in
  `default_config` / `config`:

```json
{
  "item": "li.job",
  "title": "a.title",
  "url": "a.title",
  "navigation_timeout_ms": 45000,
  "wait_until": "domcontentloaded",
  "max_retries": 2
}
```

On AWS, the worker ECS task is sized larger than api/beat (default **1024 CPU /
2048 MiB**) and pulls the `headstart-backend-worker` image. See
[deployment.md](deployment.md).

## LinkedIn / Indeed credentialed scrape ToS risk (XCT-19)

The `linkedin` and `indeed` scrapers can inject Site credentials (session
cookies / headers) to pass auth walls or Cloudflare challenges. That is
**credentialed automated access** using the member's own login session.

LinkedIn and Indeed User Agreements typically prohibit automated scraping and
similar cookie-driven access. Operators and users who store those cookies accept
**ToS / account-ban / legal exposure at their own risk** (including computer-access
statutes such as the CFAA where they apply). The Credentials UI confirms this
risk before saving LinkedIn/Indeed credentials. Guest/unauthenticated scrape
(no Site credentials) does not require that acknowledgment.

Hosted Easy Apply / auto-apply for the same adapters has a separate
`accept_private_api_risk` gate and disclosure — see
[appliers.md Safety & consent](appliers.md#safety--consent) and
[launch-checklist §7 Safety](../launch-checklist.md#7-auto-apply-optional--know-the-limits).
