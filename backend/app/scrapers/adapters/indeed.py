"""Indeed job-search adapter.

Indeed embeds search results as JSON in the HTML response:
  window.mosaic.providerData["mosaic-provider-jobcards"] = {...}

Config / context:
  - `query_url`: full Indeed search URL (e.g. `https://www.indeed.com/jobs?q=python&l=remote`).
  - `config["q"]` / `config["l"]`: keyword and location when building the search URL.
  - `config["max_results"]`: cap on jobs fetched across pages (default 50).
  - `config["page_size"]`: results per page / pagination step (default 10).

Indeed often blocks unauthenticated HTTP clients (Cloudflare). When that happens,
save session cookies via Site credentials so the shared HttpClient can pass the
challenge.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from app.scrapers.adapters.indeed_parse import parse_page, reject_captcha
from app.scrapers.base import Scraper, register_scraper
from app.scrapers.types import JobPosting, ScrapeContext

_INDEED_HOST_RE = re.compile(r"^(?:[a-z]{2}|www)\.indeed\.com$|^indeed\.com$", re.IGNORECASE)
_DEFAULT_MAX_RESULTS = 50
_DEFAULT_PAGE_SIZE = 10
_MAX_RESULTS_CAP = 1000


@register_scraper("indeed")
class IndeedScraper(Scraper):
    """Fetch postings from an Indeed keyword/location search."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        target = self._resolve(ctx)
        max_results = self._max_results(ctx.config)
        page_size = self._page_size(ctx.config)
        postings: list[JobPosting] = []
        seen: set[str] = set()
        offset = 0
        total_available: int | None = None

        while len(postings) < max_results:
            page_url = self._page_url(target.search_url, offset)
            html = self.http.get_text(page_url)
            reject_captcha(html)
            jobs, page_total = parse_page(html, target.origin)
            if total_available is None and page_total is not None:
                total_available = min(page_total, _MAX_RESULTS_CAP)
            if not jobs:
                break
            for job in jobs:
                key = job.external_id
                if key in seen:
                    continue
                seen.add(key)
                postings.append(job)
                if len(postings) >= max_results:
                    break
            offset += page_size
            if total_available is not None and offset >= total_available:
                break
            if total_available is None and len(jobs) < page_size:
                break

        return postings

    @staticmethod
    def _resolve(ctx: ScrapeContext) -> _SearchTarget:
        if ctx.query_url:
            parsed = urlparse(ctx.query_url.strip())
            host = parsed.netloc.lower()
            if not _INDEED_HOST_RE.match(host):
                raise ValueError("indeed scraper requires an indeed.com search URL")
            path = parsed.path.rstrip("/") or "/"
            if not path.startswith("/jobs"):
                raise ValueError("indeed scraper query_url must be a /jobs search page")
            origin = f"{parsed.scheme}://{parsed.netloc}"
            return _SearchTarget(search_url=ctx.query_url.strip(), origin=origin)

        config = ctx.config
        keyword = str(config.get("q") or config.get("keywords") or "").strip()
        location = str(config.get("l") or config.get("location") or "").strip()
        if not keyword and not location:
            raise ValueError("indeed scraper needs a query_url or config q/l")
        host = str(config.get("host") or "www.indeed.com").lower()
        params = {"q": keyword, "l": location, "filter": "0"}
        query = urlencode({k: v for k, v in params.items() if v})
        origin = f"https://{host}"
        return _SearchTarget(search_url=f"{origin}/jobs?{query}", origin=origin)

    @staticmethod
    def _page_url(search_url: str, start: int) -> str:
        if start <= 0:
            return search_url
        parsed = urlparse(search_url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        params["start"] = [str(start)]
        query = urlencode({k: v[0] for k, v in params.items()})
        return urlunparse(parsed._replace(query=query))

    @staticmethod
    def _max_results(config: dict[str, Any]) -> int:
        raw = config.get("max_results", _DEFAULT_MAX_RESULTS)
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            raise ValueError("max_results must be a positive integer")
        value = int(raw)
        if value <= 0:
            raise ValueError("max_results must be a positive integer")
        return min(value, _MAX_RESULTS_CAP)

    @staticmethod
    def _page_size(config: dict[str, Any]) -> int:
        raw = config.get("page_size", _DEFAULT_PAGE_SIZE)
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            raise ValueError("page_size must be a positive integer")
        value = int(raw)
        if value <= 0:
            raise ValueError("page_size must be a positive integer")
        return value


class _SearchTarget:
    __slots__ = ("search_url", "origin")

    def __init__(self, *, search_url: str, origin: str) -> None:
        self.search_url = search_url
        self.origin = origin
