"""Apple Careers (jobs.apple.com) search adapter.

Apple's careers site server-renders search results with embedded hydration JSON
in the search page HTML (``window.__staticRouterHydrationData``). Pagination uses
the ``page`` query parameter (20 jobs per page).

Config / context:
  - `query_url`: jobs.apple.com search URL.
  - `config["locale"]`: path locale (default ``en-us``).
  - `config["q"]` / `config["search"]` / `config["search_text"]`: keyword filter.
  - `config["location"]`: location slug (e.g. ``united-states-USA``) or
    ``postLocation-*`` id accepted by the site.
  - `config["company"]`: display company name (defaults to ``Apple``).
  - `config["max_results"]`: cap across pages (default 200).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from app.scrapers.adapters.apple_careers_parse import parse_search_html
from app.scrapers.base import Scraper, register_scraper
from app.scrapers.types import JobPosting, ScrapeContext

_ORIGIN = "https://jobs.apple.com"
_DEFAULT_LOCALE = "en-us"
_DEFAULT_COMPANY = "Apple"
_DEFAULT_MAX_RESULTS = 200
_MAX_RESULTS_CAP = 500
_PAGE_SIZE = 20
_HOST_RE = re.compile(r"^(?:www\.)?jobs\.apple\.com$", re.IGNORECASE)
_LOCALE_PATH_RE = re.compile(r"^/([a-z]{2}-[a-z]{2})(?:/|$)", re.IGNORECASE)


@register_scraper("apple_careers")
class AppleCareersScraper(Scraper):
    """Fetch postings from Apple Careers via server-rendered search pages."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        target = self._resolve(ctx)
        max_results = self._max_results(ctx.config)
        postings: list[JobPosting] = []
        seen: set[str] = set()
        page = 1
        total: int | None = None

        while len(postings) < max_results:
            url = self._search_url(target, page=page)
            html = self.http.get_text(url)
            page_postings, count = parse_search_html(
                html,
                company=target.company,
                locale=target.locale,
            )
            if total is None:
                total = count
            if not page_postings:
                break
            before_count = len(postings)
            for posting in page_postings:
                if posting.external_id in seen:
                    continue
                seen.add(posting.external_id)
                postings.append(posting)
                if len(postings) >= max_results:
                    break
            if len(postings) == before_count:
                break
            if total is not None and len(postings) >= total:
                break
            page += 1

        return postings

    @staticmethod
    def _resolve(ctx: ScrapeContext) -> _SearchTarget:
        company = str(ctx.config.get("company") or _DEFAULT_COMPANY)
        locale = str(ctx.config.get("locale") or _DEFAULT_LOCALE).lower()
        keyword = AppleCareersScraper._keyword(ctx)
        location = AppleCareersScraper._location(ctx)

        if ctx.query_url:
            parsed = urlparse(ctx.query_url.strip())
            host = parsed.netloc.lower()
            if not _HOST_RE.match(host):
                raise ValueError("apple_careers scraper requires a jobs.apple.com URL")
            path_locale = _LOCALE_PATH_RE.match(parsed.path)
            if path_locale:
                locale = path_locale.group(1).lower()
            if "/details/" in parsed.path:
                raise ValueError("apple_careers query_url must be a search page, not a posting")
            params = parse_qs(parsed.query, keep_blank_values=True)
            keyword = AppleCareersScraper._first_param(params, ("search", "q", "query"), keyword)
            location = AppleCareersScraper._first_param(params, ("location",), location)

        return _SearchTarget(locale=locale, keyword=keyword, location=location, company=company)

    @staticmethod
    def _search_url(target: _SearchTarget, *, page: int) -> str:
        params: dict[str, str] = {}
        if target.keyword:
            params["search"] = target.keyword
        if target.location:
            params["location"] = target.location
        if page > 1:
            params["page"] = str(page)
        query = f"?{urlencode(params)}" if params else ""
        return f"{_ORIGIN}/{target.locale}/search{query}"

    @staticmethod
    def _keyword(ctx: ScrapeContext) -> str:
        for key in ("search", "q", "search_text", "keywords", "query"):
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
        for key in ("location", "post_location", "postLocation", "location_id"):
            value = ctx.config.get(key)
            if value:
                return str(value).strip()
        value = ctx.filters.get("location")
        return str(value).strip() if value else ""

    @staticmethod
    def _first_param(
        params: dict[str, list[str]],
        keys: tuple[str, ...],
        fallback: str,
    ) -> str:
        for key in keys:
            values = params.get(key)
            if values and values[0].strip():
                return values[0].strip()
        return fallback

    @staticmethod
    def _max_results(config: dict[str, Any]) -> int:
        raw = config.get("max_results", _DEFAULT_MAX_RESULTS)
        if not isinstance(raw, int | float) or isinstance(raw, bool):
            raise ValueError("max_results must be a positive integer")
        limit = int(raw)
        if limit <= 0:
            raise ValueError("max_results must be a positive integer")
        return min(limit, _MAX_RESULTS_CAP)


@dataclass(frozen=True, slots=True)
class _SearchTarget:
    locale: str
    keyword: str
    location: str
    company: str
