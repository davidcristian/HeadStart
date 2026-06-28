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
    url: str
    posted_at: datetime | None = None
    raw: dict = {}        # original payload, for debugging

class ScrapeContext(BaseModel):
    query_url: str        # the search URL/endpoint configured by the user
    filters: dict         # arbitrary filters from the search
    config: dict          # merged source default_config + search config
```

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
| `ashby`         | Public Ashby Postings API                 | `api.ashbyhq.com/posting-api/job-board/<board>`; also accepts `jobs.ashbyhq.com/<board>` URLs |
| `generic_html`  | CSS selectors from config (selectolax)    | For simple static pages; configured in the UI |
| `playwright`    | Headless browser (base helper)            | For JS-heavy/anti-bot pages (opt-in)   |

> Prefer a site's JSON/search endpoint over HTML scraping. Reach for
> `playwright` only when necessary.

## Adding one

See [../recipes.md](../recipes.md) → "add a new job-site scraper".
Tests must use saved fixtures and never hit the network.

## Error handling

`fetch` may raise; the worker catches, logs, and records the failure against the
search without crashing. Be a polite client: real User-Agent, respect intervals,
no retry storms.

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
| `generic_html` | 2.0                  |
| `playwright`   | 5.0                  |

Limits are enforced in the shared `HttpClient` (for multi-request scrapers) and
at the start of a `playwright` fetch. Limits are per scrape run, not global
across workers.
