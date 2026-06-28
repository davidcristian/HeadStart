# Recipes

Canonical procedures for common changes. Follow these exactly so the codebase
stays uniform. Each one is self-contained, so you should not need to read
unrelated code.

---

## Recipe: add a new job-site scraper

**Goal:** be able to poll a new site (e.g. a company's careers page).

1. Create `backend/app/scrapers/adapters/<key>.py`.
2. Implement the `Scraper` base class and self-register:

   ```python
   from app.scrapers.base import Scraper, register_scraper
   from app.scrapers.types import JobPosting, ScrapeContext

   @register_scraper("acme_careers")
   class AcmeCareersScraper(Scraper):
       """Scrape ACME's public careers search endpoint."""

       def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
           data = self.http.get_json(ctx.query_url)
           return [
               JobPosting(
                   external_id=str(job["id"]),
                   title=job["title"],
                   company="ACME",
                   location=job.get("location", ""),
                   url=job["absolute_url"],
                   raw=job,
               )
               for job in data["jobs"]
           ]
   ```

3. Add a fixture + test: save a sample response under
   `backend/tests/fixtures/<key>.json` and add `backend/tests/scrapers/test_<key>.py`
   asserting it parses into the expected `JobPosting`s. **No network in tests.**
4. Classify the key in `app/core/plans.py`: add it to `FREE_SCRAPERS` or
   `PREMIUM_SCRAPERS`. Unknown keys fail closed (denied on every plan); a unit
   test asserts every registered scraper is classified.
5. Document it: add a row to [modules/scrapers.md](modules/scrapers.md).
6. Run `just check`.

That's it. No registry edits, no router edits. The adapter is discovered
automatically (adapters are imported in `app/scrapers/adapters/__init__.py`).

> Prefer a site's JSON/search endpoint. Use the `generic_html` adapter (CSS
> selectors from config) for simple pages, and only reach for Playwright
> (`PlaywrightScraper` base helper) when the page needs JS execution.

---

## Recipe: add a new notification channel

1. Create `backend/app/notifiers/adapters/<key>.py`.
2. Implement and register:

   ```python
   from app.notifiers.base import Notifier, register_notifier
   from app.notifiers.types import NotifyContext
   from app.scrapers.types import JobPosting

   @register_notifier("email")
   class EmailNotifier(Notifier):
       """Send new jobs via SMTP."""

       def send(self, ctx: NotifyContext, jobs: list[JobPosting]) -> None:
           ...
   ```

3. Add the channel's config shape to its target config and validate it in
   `app/services/target_config.py` (`_VALIDATORS` + required keys / URL checks)
   so create/update reject bad configs before persist.
4. Test with mocked I/O under `backend/tests/notifiers/`.
5. Document it in [modules/notifiers.md](modules/notifiers.md).
6. Run `just check`.

---

## Recipe: add a summarizer provider

**Goal:** generate the "why this matches" blurb with a different engine.

1. Create `backend/app/summarizers/adapters/<key>.py`.
2. Implement and register:

   ```python
   from app.summarizers.base import Summarizer, register_summarizer
   from app.summarizers.types import SummaryContext
   from app.scrapers.types import JobPosting

   @register_summarizer("acme_llm")
   class AcmeSummarizer(Summarizer):
       """One-sentence match blurbs from ACME's model."""

       def summarize(self, ctx: SummaryContext, jobs: list[JobPosting]) -> list[str]:
           return [self._call(ctx, job) for job in jobs]  # raise on failure
   ```

3. Import it in `app/summarizers/adapters/__init__.py`.
4. Read any secrets from `settings` (never `os.environ`). **Raise on failure**.
   `SummaryService` swallows it so notifications still go out.
5. Test with mocked I/O under `backend/tests/summarizers/`; no real model calls.
6. Document it in [modules/summaries.md](modules/summaries.md).

For a hosted HTTP provider, reuse the shared adapter helpers in
`app.ai.llm_common` (`extract_openai_content` / `extract_gemini_content` /
`extract_anthropic_content`, `auth_headers`, `gemini_url`, `gemini_headers`)
instead of re-implementing response parsing or auth. Never put the API key in
the URL. These helpers back every AI family (summarizers, resumes, cover
letters, email classifiers, reply drafters), and each family's `base.py`
registry is the generic `app.ai.registry.AdapterRegistry`, so the same recipe
applies to the other families (`register_<family>` / `get_<family>`).

Select a provider at runtime with `SUMMARY_PROVIDER=<key>`.

---

## Recipe: add a new apply adapter

**Goal:** let users submit (or preview) applications on a job board.

1. Create `backend/app/appliers/adapters/<key>.py`.
2. Implement the `Applier` base class and self-register:

   ```python
   from app.appliers.base import Applier, register_applier
   from app.appliers.types import ApplyContext, ApplyResult

   @register_applier("greenhouse")
   class GreenhouseApplier(Applier):
       """Submit applications via the Greenhouse Job Board API."""

       def apply(self, ctx: ApplyContext) -> ApplyResult:
           payload = self._build_payload(ctx)
           if ctx.dry_run:
               return ApplyResult(status="dry_run", payload=payload)
           ...
   ```

3. Import the module in `app/appliers/adapters/__init__.py`.
4. Add a fixture + test under `backend/tests/appliers/test_<key>.py`. **No
   network in tests.**
5. Document it in [modules/appliers.md](modules/appliers.md).
6. Run `just check`.

The `key` should match the scraper `adapter_key` when the same site supports
both scrape and apply. `ApplyService` resolves appliers by the job's source
`adapter_key`.

---

## Recipe: add a curated portal preset

**Goal:** list a new employer in the portal catalog and one-click Sources UI.

1. Confirm the employer's public careers API works with an existing scraper
   (use `POST /sources/detect`, or follow the scraper recipe to add one first).
2. Add `backend/app/portals/presets/<portal_id>.py` exporting a single `PORTAL`
   (use helpers from `catalog_helpers.py`: `gh_preset`, `lever_preset`,
   `ashby_preset`, `workday_preset`, `icims_preset`, etc.; Phenom uses
   `phenom_preset` in `catalog_helpers_phenom.py`; Rippling uses
   `rippling_preset` in `catalog_helpers_rippling.py`; IBM Careers keyword
   brands use `ibm_careers_preset` in `catalog_helpers_ibm.py`; Workable uses
   `workable_preset` in `catalog_helpers_workable.py`; SuccessFactors uses
   `successfactors_preset` in `catalog_helpers_successfactors.py`). Register it in
   `presets/__init__.py` and append `*PORTALS` in `catalog_presets.py`. Add it
   inline in `catalog_presets.py` instead when the catalog is still small.
3. Pick a unique `portal_id` and `category` (`big_tech`, `unicorn`, `ai`).
4. Document the count/category breakdown in [modules/portals.md](modules/portals.md)
   if the catalog composition changed materially.
5. Run `just check`.

No registry or router edits are needed. The catalog is static data consumed by
`PortalCatalogService` and `PortalSearchService`.

---

## Recipe: add an API endpoint

1. Schema: add request/response models in `backend/app/schemas/`.
2. Repository: add query methods in `backend/app/repositories/` (DB access only).
3. Service: add business logic in `backend/app/services/`.
4. Router: add the route in `backend/app/api/v1/<resource>.py`; it should only
   parse input, call the service, and return the schema.
5. Tests: cover the service and the route.
6. Document it in [modules/api.md](modules/api.md).

Never let a router touch the DB directly.

---

## Recipe: change the data model (migration)

1. Edit the ORM model in `backend/app/models/`.
2. Generate a migration: `just makemigration "add column x to search"`.
3. Review the generated file under `backend/alembic/versions/` (autogenerate is
   a starting point, not gospel).
4. Apply locally: `just migrate`.
5. Verify Postgres compatibility: `just test-migrations` (needs docker). Unit
   tests run on SQLite `create_all`, so any raw SQL in a migration must be
   written for **both** dialects. For example, compare booleans with
   `TRUE`/`FALSE`, never `= 1`/`= 0`, and keep revision ids ≤ 32 chars
   (`alembic_version.version_num` is `varchar(32)` on Postgres). CI runs this
   gate on every push: `alembic upgrade head` on empty Postgres 16,
   then `alembic check` so models cannot drift from migrations.
6. Update [modules/data-model.md](modules/data-model.md).

---

## Recipe: add a config value

1. Add the field to `Settings` in `backend/app/core/config.py` with a default.
2. Add it to `.env.example` with a comment.
3. Use it via the settings object. Never read `os.environ` directly elsewhere.

---

## Recipe: record a decision (ADR)

Copy [adr/0000-template.md](adr/0000-template.md) to
`adr/NNNN-short-title.md`, fill it in, and link it from the relevant doc.
