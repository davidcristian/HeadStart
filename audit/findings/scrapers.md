# Scrapers — job-board fetch/normalize adapters

This area covers the pluggable scraper adapters under `backend/app/scrapers/` — the HTTP client, per-site fetch/parse code, and the URL-detection logic that classifies onboarded source URLs. The audit found no critical or high issues, but a consistent theme of insufficient hardening against untrusted upstream input: several adapters parse epoch timestamps and counts without guarding the numeric-conversion edge cases (Infinity/NaN/overflow), the shared HTTP client reads response bodies with no size cap, a Shopify stream resolver recurses unbounded, and two URL detectors match hosts too loosely. Individually these are recoverable per-search failures or onboarding misclassifications, but they reflect a parse-path that trusts upstream JSON/HTML more than it should.

**Summary:** 0 critical · 0 high · 2 medium · 4 low (6 findings; three duplicate records for the `fromtimestamp` defect merged into SCR-02).

---

<a id="scr-02"></a>
### SCR-02 — Unguarded fromtimestamp on untrusted epoch aborts whole scrape (4 adapters)
🟡 **MEDIUM** · 🐞 bug · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/65)) · Confidence: high (5/5 verifiers) · Effort: S · WS34

**Update (2026-07-10).** Fixed in [PR](https://github.com/davidcristian/HeadStart/pull/65): shared `parse_epoch_seconds` / `parse_epoch_millis` catch `OverflowError`/`OSError`/`ValueError` from `fromtimestamp`; Google, Microsoft, Lever, and Indeed posted-at paths use them so one hostile epoch degrades to `None` instead of aborting the page.

> Merged from three records (SCR-01, SCR-02, SCR-03) describing the same defect across the same set of adapters. The highest-verified record (5/5) is used as the canonical entry.

**Locations:** `backend/app/scrapers/adapters/google_careers_parse.py:151` (`_posted_at_from_record`); plus:
- `backend/app/scrapers/adapters/microsoft_careers.py:219` (`_posted_at`, `postedTs`)
- `backend/app/scrapers/adapters/lever.py:90` (`_to_posting`, `createdAt/1000`)
- `backend/app/scrapers/adapters/indeed_parse.py:127` (`pub_date/1000`)

**Evidence.** Each adapter calls `datetime.fromtimestamp(float(seconds), tz=UTC)` after only an `isinstance(seconds, int | float)` check. `datetime.fromtimestamp` raises `OverflowError`/`OSError` (not `ValueError`) on out-of-range values, and none of these call sites catch it. Verified that `fromtimestamp(1e30)` raises `OverflowError` and values like `1e20`, `-1e20`, and `99999999999999` raise `OSError`/`OverflowError`/`ValueError`. `json.loads` will also accept `Infinity`, so an upstream number can pass the `isinstance` guard and still overflow. The WS6 `dates.parse_iso8601` degrade-to-None pattern was never applied to the epoch path.

**Failure scenario.** Upstream returns a single posting with a huge or negative epoch (e.g. `postedTs=1e20` or `createdAt=1e21`). `fromtimestamp` raises `OverflowError`, which propagates out of the top-level list comprehension / parse loop in `fetch()`/`parse_page`, so the entire scrape run for that search fails and none of the page's postings are ingested that tick.

**Suggested fix.** Route every epoch parse through a shared lenient helper (mirroring `dates.parse_iso8601`) that catches `OverflowError`, `OSError`, and `ValueError` and returns `None`, degrading a single bad posting instead of aborting the batch.

**Verification.** Confirmed 5/5 adversarial verifiers. Verified `fromtimestamp` raises `OverflowError`/`OSError` on huge epochs; all four adapters guard only with `isinstance(int|float)` and have no try/except; per-search isolated but drops the whole page's jobs each tick.

<a id="scr-04"></a>
### SCR-04 — Scraper HTTP client reads unbounded response bodies — hostile upstream can OOM worker
🟡 **MEDIUM** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/66)) · Confidence: high (3/3 verifiers) · Effort: M · WS34

**Update (2026-07-10).** Fixed in [PR](https://github.com/davidcristian/HeadStart/pull/66): `HttpClient` streams all responses, rejects oversized `Content-Length` up front, and raises `ResponseTooLargeError` once streamed bytes exceed `SCRAPER_MAX_RESPONSE_BYTES` (default 5 MiB).

**Locations:** `backend/app/scrapers/http.py:44` (`HttpClient.get_text`/`get_json`); plus:
- `backend/app/scrapers/adapters/generic_html.py:40`
- `backend/app/scrapers/adapters/indeed_parse.py:149`

**Evidence.** `get_text`/`get_json` call `resp.text`/`resp.json()` with no max-size limit, and the underlying `httpx.Client` is constructed with no `limits`/streaming cap. `get_text` feeds its result straight into a selectolax `HTMLParser(html)`. A grep of `http.py` and `config.py` finds no body-size setting anywhere. The existing `outbound_url` guard only blocks private IP ranges, not arbitrary public hosts, so an authenticated user's `query_url` can point at any host they control.

**Failure scenario.** A user points a `query_url` at a host they control that streams a multi-GB body or giant HTML document. The Celery worker buffers and parses the entire body in memory, exhausting RAM and killing the worker — which is shared across all tenants.

**Suggested fix.** Stream responses and enforce a max byte cap (abort once past N MB) before calling `.text`/`.json()`; reject an overly large `Content-Length` up front.

**Verification.** Confirmed 3/3 adversarial verifiers. `get_text`/`get_json` read `resp.text`/`resp.json()` with no size cap and httpx has no limits; the `outbound_url` guard only blocks private IPs, so an authed user's `query_url` can OOM the shared worker.

<a id="scr-05"></a>
### SCR-05 — int() of untrusted total crashes on JSON Infinity/NaN in 4 adapters
⚪ **LOW** · 🐞 bug · Status: ✅ done · Confidence: high (5/5 verifiers) · Effort: S · WS34

**Locations:** `backend/app/scrapers/adapters/apple_careers_parse.py:52` (`parse_search_html`); plus:
- `backend/app/scrapers/adapters/workday.py:67`
- `backend/app/scrapers/adapters/amazon_jobs.py:195`
- `backend/app/scrapers/adapters/microsoft_careers.py:168`

**Evidence.** Each adapter does `int(raw_total) if isinstance(raw_total, (int, float))`. `json.loads` accepts `Infinity` and `NaN` as floats, so both pass the `isinstance` check; then `int(inf)` raises `OverflowError` and `int(nan)` raises `ValueError`. `smartrecruiters._coerce_count` (line 116) already added a `math.isfinite` guard in WS6, but these four sibling adapters were never updated to match.

**Failure scenario.** Upstream JSON returns `total`/`hits`/`count = Infinity` or `NaN`; `int()` raises, `fetch()` aborts, and the entire scrape run for that search fails.

**Suggested fix.** Route all total/count coercions through a shared finite-checked helper, reusing the `smartrecruiters._coerce_count` pattern with `math.isfinite`.

**Verification.** Confirmed 5/5 adversarial verifiers. `json.loads` accepts Infinity/NaN and `int(inf)`/`int(nan)` raise; `smartrecruiters._coerce_count` added `math.isfinite` in WS6 but the apple/workday/amazon/microsoft siblings still do bare `int(raw)` on isinstance-only checks.

<a id="scr-06"></a>
### SCR-06 — Shopify flight-stream resolver recurses with no depth bound (RecursionError DoS)
⚪ **LOW** · 🐞 bug · Status: ✅ done · Confidence: medium (5/5 verifiers) · Effort: S · WS34

**Locations:** `backend/app/scrapers/adapters/shopify_careers_parse.py:61` (`_resolve_node`).

**Evidence.** `_resolve_node` recurses per referenced index/list/dict with only a per-path visited-set (a cycle guard) and no maximum depth. A deeply nested untrusted React-Router flight stream — a long non-cyclic reference chain `a -> b -> c -> ...` — drives the recursion depth to the length of the array, which can exceed Python's recursion limit.

**Failure scenario.** Shopify (or a spoofed careers page reached via cookies/redirect) serves a stream with a long non-cyclic reference chain; `_resolve_node` hits Python's recursion limit and raises `RecursionError`, aborting the `shopify_careers` scrape.

**Suggested fix.** Add a max-depth argument to `_resolve_node` and return the raw value (or `None`) once it is exceeded, matching the graceful-degrade contract of the other parsers.

**Verification.** Confirmed 5/5 adversarial verifiers. `_resolve_node` recurses per int ref with a per-path cycle guard but no max-depth; a long non-cyclic chain in an untrusted stream can hit Python's recursion limit; isolated per-search and self-healing, so low as rated.

<a id="scr-07"></a>
### SCR-07 — Ashby detector matches any host when path contains 'posting-api/job-board'
⚪ **LOW** · 🐞 bug · Status: ✅ done · Confidence: high (3/3 verifiers) · Effort: XS · WS34

**Locations:** `backend/app/scrapers/url_detect.py:110` (`_detect_ashby`).

**Evidence.** The guard reads `if host != "jobs.ashbyhq.com" and "posting-api/job-board" not in parsed.path: return None` — so any arbitrary host whose path merely contains that substring is accepted. Verified that `https://evil.example.com/posting-api/job-board/acme` yields `adapter_key='ashby'`. There is no host allowlist on the API-path branch.

**Failure scenario.** A user onboards an unrelated URL that happens to contain `posting-api/job-board` in its path; detection mislabels it as the Ashby adapter and rewrites `base_url` to `jobs.ashbyhq.com/<board>`, producing a wrong-provider source.

**Suggested fix.** Gate the API-path branch to Ashby-owned hosts (e.g. `host.endswith(".ashbyhq.com")`) before extracting the board slug.

**Verification.** Confirmed 3/3 adversarial verifiers. `_detect_ashby` accepts any host whose path contains `posting-api/job-board` with no host allowlist; reachable via `/sources/detect`, mislabels arbitrary hosts as Ashby; no upstream guard.

**Fix.** `_detect_ashby` requires `jobs.ashbyhq.com` or an `*.ashbyhq.com` host with `posting-api/job-board` in the path — [PR](https://github.com/davidcristian/HeadStart/pull/173).

<a id="scr-08"></a>
### SCR-08 — Microsoft careers host match uses suffix endswith without dot boundary (over-broad)
⚪ **LOW** · 🔒 security · Status: ✅ done · Confidence: high (3/3 verifiers) · Effort: XS · WS34

**Locations:** `backend/app/scrapers/url_detect_microsoft.py:15` (`detect_microsoft_careers`).

**Evidence.** The check `if not host.endswith("careers.microsoft.com")` matches `evilcareers.microsoft.com` and `xcareers.microsoft.com` because there is no leading dot or anchor. Verified that both return a Microsoft `SourceDetection`. Sibling detectors anchor hosts properly (indeed uses `.indeed.com`; others use compiled `^...$` regexes).

**Failure scenario.** A user pastes/onboards a lookalike host such as `evilcareers.microsoft.com`; `/sources/detect` confidently classifies it as the Microsoft adapter and suggests Microsoft config, mis-onboarding a non-Microsoft/phishing host.

**Suggested fix.** Match exactly `careers.microsoft.com`, or require a `.careers.microsoft.com` dot-boundary suffix, mirroring the anchored regex pattern used by the sibling detectors.

**Verification.** Confirmed 3/3 adversarial verifiers. `detect_microsoft_careers` uses `host.endswith('careers.microsoft.com')` with no dot boundary, matching `evilcareers.microsoft.com`; reachable via `/sources/detect` with no upstream host anchor; siblings anchor properly.
