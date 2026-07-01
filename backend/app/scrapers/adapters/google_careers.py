"""Google Careers job-search adapter.

Google's careers portal embeds search results as JSON inside the HTML response:
  AF_initDataCallback({key: 'ds:1', ... data: [...] ...})

Config / context:
  - `query_url`: full careers search URL or the board root.
  - `config["q"]` / `config["search_text"]`: keyword filter when building the URL.
  - `config["location"]`: optional location filter.
  - `config["company"]`: display company name (defaults to ``Google``).
  - `config["max_results"]`: cap on jobs fetched across pages (default 100).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from app.scrapers.adapters.google_careers_parse import parse_search_page
from app.scrapers.base import Scraper, register_scraper
from app.scrapers.types import JobPosting, ScrapeContext

_APPLICATIONS_BASE = "https://www.google.com/about/careers/applications"
_RESULTS_PATH = "/jobs/results/"
_HOST_RE = re.compile(
    r"^(?:www\.)?google\.com$|^careers\.google\.com$",
    re.IGNORECASE,
)
_DEFAULT_MAX_RESULTS = 100
_MAX_RESULTS_CAP = 500
_PAGE_SIZE = 20


@register_scraper("google_careers")
class GoogleCareersScraper(Scraper):
    """Fetch postings from Google Careers search results pages."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        target = self._resolve(ctx)
        max_results = self._max_results(ctx.config)
        postings: list[JobPosting] = []
        seen: set[str] = set()
        page = 1

        while len(postings) < max_results:
            page_url = self._page_url(target.search_url, page)
            html = self.http.get_text(page_url)
            page_jobs = parse_search_page(
                html,
                company=target.company,
                applications_base=_APPLICATIONS_BASE,
                query_params=target.query_params,
            )
            if not page_jobs:
                break
            for job in page_jobs:
                if job.external_id in seen:
                    continue
                seen.add(job.external_id)
                postings.append(job)
                if len(postings) >= max_results:
                    break
            if len(page_jobs) < _PAGE_SIZE:
                break
            page += 1

        return postings

    @staticmethod
    def _resolve(ctx: ScrapeContext) -> _SearchTarget:
        company = str(ctx.config.get("company") or "Google")
        keyword = GoogleCareersScraper._keyword(ctx)
        location = GoogleCareersScraper._location(ctx)
        query_params = GoogleCareersScraper._query_params(keyword, location)

        if ctx.query_url:
            search_url = GoogleCareersScraper._normalize_search_url(
                ctx.query_url,
                keyword=keyword,
                location=location,
            )
            parsed = urlparse(search_url)
            params = parse_qs(parsed.query, keep_blank_values=True)
            query_params = {k: v[0] for k, v in params.items() if v and v[0]}
            return _SearchTarget(
                search_url=GoogleCareersScraper._search_url_without_page(search_url),
                company=company,
                query_params=query_params,
            )

        if not keyword and not location:
            raise ValueError(
                "google_careers scraper needs a query_url or config.q / config.location"
            )
        return _SearchTarget(
            search_url=GoogleCareersScraper._build_search_url(keyword, location),
            company=company,
            query_params=query_params,
        )

    @staticmethod
    def _keyword(ctx: ScrapeContext) -> str:
        for key in ("q", "search_text", "keywords"):
            value = ctx.config.get(key)
            if value:
                return str(value).strip()
        for key in ("keywords_include", "keywords"):
            value = ctx.filters.get(key)
            if value:
                return str(value).strip()
        return ""

    @staticmethod
    def _location(ctx: ScrapeContext) -> str:
        for key in ("location", "l"):
            value = ctx.config.get(key)
            if value:
                return str(value).strip()
        value = ctx.filters.get("location")
        return str(value).strip() if value else ""

    @staticmethod
    def _query_params(keyword: str, location: str) -> dict[str, str]:
        params: dict[str, str] = {}
        if keyword:
            params["q"] = keyword
        if location:
            params["location"] = location
        return params

    @staticmethod
    def _build_search_url(keyword: str, location: str) -> str:
        params = GoogleCareersScraper._query_params(keyword, location)
        query = urlencode(params)
        return f"{_APPLICATIONS_BASE}{_RESULTS_PATH}?{query}"

    @staticmethod
    def _normalize_search_url(query_url: str, *, keyword: str, location: str) -> str:
        parsed = urlparse(query_url.strip())
        host = parsed.netloc.lower()
        if not _HOST_RE.match(host):
            raise ValueError("google_careers scraper requires a google.com careers URL")
        path = parsed.path.rstrip("/") or "/"
        if path.endswith("/jobs/results"):
            params = parse_qs(parsed.query, keep_blank_values=True)
            if keyword and not (params.get("q") or [""])[0]:
                params["q"] = [keyword]
            if location and not (params.get("location") or [""])[0]:
                params["location"] = [location]
            query = urlencode({k: v[0] for k, v in params.items() if v})
            return urlunparse(parsed._replace(path=f"{path}/", query=query))
        if host == "careers.google.com" and path in {"/", ""}:
            return GoogleCareersScraper._build_search_url(keyword, location)
        raise ValueError("google_careers query_url must be a /jobs/results search page")

    @staticmethod
    def _search_url_without_page(search_url: str) -> str:
        parsed = urlparse(search_url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        params.pop("page", None)
        query = urlencode({k: v[0] for k, v in params.items() if v})
        return urlunparse(parsed._replace(query=query))

    @staticmethod
    def _page_url(search_url: str, page: int) -> str:
        parsed = urlparse(search_url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        params["page"] = [str(page)]
        query = urlencode({k: v[0] for k, v in params.items() if v})
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


@dataclass(frozen=True, slots=True)
class _SearchTarget:
    search_url: str
    company: str
    query_params: dict[str, str]
