# Module: Curated portals

**Path:** `backend/app/portals/`

Static catalog of employer career portals (FAANG-adjacent, unicorns, AI labs)
with one-click source setup and a Pro+ cross-portal search page. Each preset
maps to an existing scraper adapter with verified public API access.

## Catalog

Presets live in `catalog_presets.py` (data) and `catalog_helpers.py` (factory
helpers). Each `PortalPreset` carries:

| Field | Purpose |
| ----- | ------- |
| `id` | Stable slug used in API and `default_config.portal_id` |
| `company_name` | Display name in the UI |
| `category` | `big_tech`, `unicorn`, or `ai` |
| `adapter_key` | Scraper key (`greenhouse`, `lever`, `ashby`, `workday`, `apple_careers`, `google_careers`, `microsoft_careers`) |
| `base_url` | Careers board URL passed to the scraper |
| `default_config` | Adapter-specific config merged into new sources (always includes `portal_id`) |

As of the current catalog: **68 employers** — 29 big tech, 28 unicorn, 11 AI —
across Greenhouse (39), Ashby (11), Workday (9), Lever (4), Apple Careers (1),
Google Careers (1), Meta Careers (1), Microsoft Careers (1), and Amazon Jobs (1).
Meta uses the `meta_careers` scraper (Relay GraphQL search on metacareers.com).
Apple uses the `apple_careers` scraper (hydration JSON embedded in search HTML).

`GET /portals` annotates each row with:

- `supports_auto_apply` — whether a registered apply adapter exists for the scraper key
- `allowed_on_plan` — whether the user's plan may use that scraper (see [auth.md](auth.md))
- `already_added` — duplicate detection against owned sources

Duplicate detection matches `portal_id` in `default_config`, normalized
`base_url`, or adapter-specific identity fields (e.g. `board_token` for
Greenhouse, `tenant`+`site` for Workday).

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
| Sources catalog | `/app/sources` | Browse/filter presets; **Add source** pre-fills adapter + config |
| Companies search | `/app/portals` | Pro+ keyword search across the catalog; preview results; one-click alert setup |

Free users see the catalog on Sources but cannot open `/app/portals` (upgrade
prompt). Presets whose scraper is premium-only (`indeed`, `linkedin`,
`playwright`) are not in this catalog.

## Adding a preset

1. Confirm the employer's public careers API works with an existing scraper
   (test with `POST /sources/detect` or a unit-test fixture).
2. Add a factory call in `catalog_presets.py` using the helpers in
   `catalog_helpers.py` (`gh_preset`, `lever_preset`, `ashby_preset`,
   `workday_preset`, `google_careers_preset`, `microsoft_careers_preset`).
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
