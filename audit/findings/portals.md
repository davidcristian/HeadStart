# Curated employer portals catalog

This area covers the curated employer-portal catalog under `backend/app/portals/` — the preset builders and catalog definitions (`catalog_helpers.py`, `catalog_presets.py`, `catalog.py`) that seed single-employer and board-backed scraper configurations. The audit found one confirmed issue: the `shopify_careers` preset ships a dead `board` config key that no scraper code path ever reads. No correctness or security defects were found; the catalog wiring is otherwise sound.

**Summary (this area):** 🔴 critical: 0 · 🟠 high: 0 · 🟡 medium: 0 · ⚪ low: 1

---

<a id="por-01"></a>
### POR-01 — shopify_careers preset ships a dead default_config key `board` the scraper never reads
⚪ **LOW** · ♻️ refactor · Status: ☐ open · Confidence: high (3/3 verifiers) · Effort: XS · WS35

> Merged: POR-01 and POR-02 are the same defect (the inert `board` key in `shopify_careers_preset`), reported once as a refactor and once as a consistency issue. Rendered here as a single finding.

**Locations:** `backend/app/portals/catalog_helpers.py:186` (`shopify_careers_preset`); also `backend/app/portals/catalog_helpers.py:189`; plus `backend/app/scrapers/adapters/shopify_careers.py:47` and `backend/app/portals/catalog_presets.py:29`.

**Evidence.** `shopify_careers_preset` sets `default_config={"company", "portal_id", "board": "shopify"}`, but the Shopify scraper only ever reads the config keys `q`/`search`/`search_text`/`company`/`max_results` — a grep for `board` across `shopify_careers.py` and `shopify_careers_parse.py` returns zero hits. The key was copy-pasted from `snowflake_careers_preset`, where `board` is genuinely consumed (via `config.get("board")`) by the Ashby-backed scraper. In the single-employer Shopify preset the value is inert.

**Failure scenario.** No runtime impact: the key is silently ignored. A user adding the Shopify portal stores a `board` key no code path consumes, and a maintainer is misled into thinking Shopify's board slug is configurable — diverging from the config shape of every other single-employer preset.

**Suggested fix.** Drop the `board` entry from `shopify_careers_preset` default_config (keep `company` + `portal_id`) so the stored config matches what the Shopify scraper actually reads.

**Verification.** Confirmed 3/3 adversarial verifiers. Verifiers grepped both Shopify scraper files and found 0 occurrences of `board`; classed as a harmless-but-misleading dead-config / consistency issue, low severity.
