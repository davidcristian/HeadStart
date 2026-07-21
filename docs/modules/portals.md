# Module: Curated portals

**Path:** `backend/app/portals/`

Static catalog of employer career portals (FAANG-adjacent, unicorns, AI labs)
with one-click source setup and a Pro+ cross-portal search page. Each preset
maps to an existing scraper adapter with verified public API access.

## Catalog

Presets live in `catalog_presets.py` (core catalog), `presets/` (one module per
employer portal, e.g. `presets/hubspot.py`), and `catalog_helpers.py` (factory
helpers). Each `PortalPreset` carries:

| Field | Purpose |
| ----- | ------- |
| `id` | Stable slug used in API and `default_config.portal_id` |
| `company_name` | Display name in the UI |
| `category` | `big_tech`, `unicorn`, or `ai` |
| `adapter_key` | Scraper key (`greenhouse`, `lever`, `ashby`, `workday`, `smartrecruiters`, `apple_careers`, `google_careers`, `microsoft_careers`, `shopify_careers`, `snowflake_careers`, `uber_careers`, `icims`, `phenom`, `rippling`, `ibm_careers`, `workable`) |
| `base_url` | Careers board URL passed to the scraper |
| `default_config` | Adapter-specific config merged into new sources (always includes `portal_id`) |

As of the current catalog: **166 employers** — 59 big tech, 86 unicorn, 21 AI —
across Greenhouse (84), Ashby (31), Workday (15), SmartRecruiters (14), Lever (4),
Apple Careers (1), Google Careers (1), Meta Careers (1), Microsoft Careers (1),
Shopify Careers (1), Snowflake Careers (1), Uber Careers (1), Amazon Jobs (1),
iCIMS/Jibe (1), Phenom (4), Rippling ATS (1), IBM Careers (2), and Workable (2).
Meta uses the `meta_careers` scraper (Relay GraphQL search on metacareers.com).
Apple uses the `apple_careers` scraper (hydration JSON embedded in search HTML).
Shopify Careers (`shopify_careers`) stores only `company` + `portal_id` in
`default_config` — the scraper reads those (plus optional `q` / `max_results`);
it does **not** take an Ashby `board` slug. Auto-apply still defaults
`board=shopify` inside the applier when delegating to Ashby. Snowflake Careers
keeps `board` because its Ashby-backed scraper consumes it. Rivian uses the
`icims` scraper (`careers_base_url` + public `/api/jobs`). Grammarly uses Ashby
with board `Superhuman Platform Inc` (Grammarly careers redirect to Superhuman;
`portal_id` stays `grammarly`). Snyk uses Workday (`tenant=snyk`, `site=External`,
`region=wd103`); the marketing careers page at `snyk.io/careers` proxies the same
board via `/api/next/jobs`. Snap uses Workday on
`wd1.myworkdaysite.com/recruiting/snapchat/snap` (`host_kind=site`; paste
`careers.snap.com` also detects). HashiCorp and Red Hat use `ibm_careers` keyword
search (post-acquisition roles live on IBM Careers). CVS Health, GE HealthCare,
and RTX use Phenom (`jobs.cvshealth.com`, `careers.gehealthcare.com`,
`careers.rtx.com`). Box uses Greenhouse board token `boxinc` with
`portal_id=box`. Hugging Face and Skroutz use Workable (`account=huggingface`,
`account=skroutz`). Wise uses SmartRecruiters (`company_id=Wise`,
`portal_id=wise`). 1Password uses Ashby board `1password` with
`portal_id=onepassword`. Phase 34 batch 8 adds Together AI (`togetherai` /
`portal_id=together`), Modal, Anyscale, Runway, Character.AI (`board=character` /
`portal_id=characterai`), Midjourney, Pinecone, Grafana Labs (`grafanalabs` /
`portal_id=grafana`), Temporal, PostHog, Neon, PlanetScale, Faire, Gong
(`gongio` / `portal_id=gong`), and Checkout.com (`board=checkout.com` /
`portal_id=checkout`).

`GET /portals` annotates each row with:

- `supports_auto_apply` — whether a registered apply adapter exists for the scraper key
- `allowed_on_plan` — whether the user's plan may use that scraper (see [auth.md](auth.md))
- `already_added` — duplicate detection against owned sources

Duplicate detection matches `portal_id` in `default_config`, normalized
`base_url`, or adapter-specific identity fields (e.g. `board_token` for
Greenhouse, `company_id` for SmartRecruiters, `tenant`+`site` for Workday).

## API (prefix `/api/v1/portals`)

| Method | Path | Plan | Purpose |
| ------ | ---- | ---- | ------- |
| GET | `/` | any verified user | List catalog (`category`, `q` query filters) |
| POST | `/search` | Pro+ (`portal_search`) | Scrape curated portals once; return keyword-filtered matches |
| POST | `/subscribe` | Pro+ (`portal_search`) | Bulk-create sources + searches for selected portals |

All portal routes require a **verified** email (`get_verified_user`).

### Cross-portal search (`POST /search`)

Request body (`PortalSearchRequest`):

- `keywords` (required) — applied as search filters after each portal scrape
- `category` — optional filter to one catalog category
- `portal_ids` — optional subset (max 30); defaults to all allowed presets on the user's plan
  (the Companies UI caps selection at 30 — default / Select-all take the first 30 in catalog
  order — so Search / Subscribe never 422 on the happy path)
- `location`, `workplace` — optional structured filters (same semantics as search filters)

The service scrapes each portal via `PipelineService.scrape` (no DB writes),
applies posting filters, and returns up to **10 jobs per portal** and **100 total**.
Per-portal failures are collected in `errors` without failing the whole request.

### Bulk alert setup (`POST /subscribe`)

Creates missing sources from presets, then one enabled search per portal with
the given `keywords`, `target_id`, `interval_seconds`, and notification mode.
Portals the user already owns are skipped (`skipped_portal_ids`). Respects plan
source/search caps — may return a partial result with a `message` when limits
are hit.

## Frontend surfaces

| Surface | Path | Purpose |
| ------- | ---- | ------- |
| Sources catalog | `/app/sources` | Browse/filter presets (category filters: labelled button group with `aria-pressed`, not a bare tablist — FRO-41); **Add source** pre-fills adapter + config |
| Companies search | `/app/portals` | Pro+ keyword search across the catalog (same category button group; max 30 portals per request); preview results; one-click alert setup |

Free users see the catalog on Sources but cannot open `/app/portals` (upgrade
prompt). The Portals page reads `plan.features.portal_search` from `GET /meta`
(Pro only) before enabling cross-portal search; the API still enforces
`require_portal_search` server-side. Presets whose scraper is premium-only
(`indeed`, `linkedin`, `playwright`) are not in this catalog.

## Adding a preset

1. Confirm the employer's public careers API works with an existing scraper
   (test with `POST /sources/detect` or a unit-test fixture).
2. Add `presets/<portal_id>.py` exporting `PORTAL` (use helpers in
   `catalog_helpers.py`: `gh_preset`, `lever_preset`, `ashby_preset`,
   `sr_preset`, `workday_preset`, `icims_preset`, etc.; Phenom uses
   `phenom_preset` from `catalog_helpers_phenom.py`; Rippling uses
   `rippling_preset` from `catalog_helpers_rippling.py`; IBM Careers keyword
   brands use `ibm_careers_preset` from `catalog_helpers_ibm.py`; Workable
   accounts use `workable_preset` from `catalog_helpers_workable.py`). Register it in `presets/__init__.py`.
3. Set a unique `portal_id` in `default_config` (the factory helpers do this
   automatically).
4. Pick `category` (`big_tech`, `unicorn`, `ai`).
5. Add a regression test if search/subscribe behaviour depends on the new entry.

No registry or router changes are needed — the catalog is static data consumed
by `PortalCatalogService` and `PortalSearchService`.

## Related docs

- Scrapers used by presets: [scrapers.md](scrapers.md)
- Apply adapters (when `supports_auto_apply` is true): [appliers.md](appliers.md)
- Plan gate for `/portals/search`: [auth.md](auth.md) (`portal_search` feature)
- API route table: [api.md](api.md)
