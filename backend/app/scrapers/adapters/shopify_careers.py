"""Shopify Careers adapter.

Shopify hosts careers on shopify.com/careers with Ashby behind the scenes, but the
public Ashby Postings API is disabled. The careers page server-renders a React
Router flight stream containing ``jobPostingsWithJobs``.

Config / context:
  - `query_url`: ``https://www.shopify.com/careers`` search URL (optional).
  - `config["q"]` / `config["search"]` / `config["search_text"]`: client-side
    keyword filter applied after fetch.
  - `config["company"]`: display company name (defaults to ``Shopify``).
  - `config["max_results"]`: cap on jobs returned (default 500).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from app.scrapers.adapters.shopify_careers_parse import parse_careers_html
from app.scrapers.base import Scraper, register_scraper
from app.scrapers.types import JobPosting, ScrapeContext

_ORIGIN = "https://www.shopify.com/careers"
_DEFAULT_COMPANY = "Shopify"
_DEFAULT_MAX_RESULTS = 500
_MAX_RESULTS_CAP = 1000
_HOST_RE = re.compile(r"^(?:www\.)?shopify\.com$", re.IGNORECASE)


@register_scraper("shopify_careers")
class ShopifyCareersScraper(Scraper):
    """Fetch postings from Shopify Careers via embedded loader data."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        target = self._resolve(ctx)
        html = self.http.get_text(target.search_url)
        postings = parse_careers_html(html, company=target.company)
        if target.keyword:
            postings = [job for job in postings if self._matches_keyword(job, target.keyword)]
        return postings[: self._max_results(ctx.config)]

    @staticmethod
    def _resolve(ctx: ScrapeContext) -> _SearchTarget:
        company = str(ctx.config.get("company") or _DEFAULT_COMPANY)
        keyword = ShopifyCareersScraper._keyword(ctx)
        search_url = _ORIGIN

        if ctx.query_url:
            parsed = urlparse(ctx.query_url.strip())
            host = parsed.netloc.lower()
            if not _HOST_RE.match(host):
                raise ValueError("shopify_careers scraper requires a shopify.com/careers URL")
            if not parsed.path.rstrip("/").startswith("/careers"):
                raise ValueError("shopify_careers query_url must point at the careers section")
            search_url = ctx.query_url.strip()

        return _SearchTarget(search_url=search_url, keyword=keyword, company=company)

    @staticmethod
    def _keyword(ctx: ScrapeContext) -> str:
        for key in ("q", "search", "search_text", "keywords", "query"):
            value = ctx.config.get(key)
            if value:
                return str(value).strip().lower()
        for key in ("keywords_include", "keywords"):
            value = ctx.filters.get(key)
            if value:
                return str(value).strip().lower()
        return ""

    @staticmethod
    def _matches_keyword(job: JobPosting, keyword: str) -> bool:
        haystack = " ".join(
            part
            for part in (
                job.title,
                job.location,
                str(job.raw.get("teamName") or ""),
                str(job.raw.get("departmentName") or ""),
            )
            if part
        ).lower()
        return keyword in haystack

    @staticmethod
    def _max_results(config: dict[str, Any]) -> int:
        raw = config.get("max_results", _DEFAULT_MAX_RESULTS)
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            raise ValueError("max_results must be a positive integer")
        limit = int(raw)
        if limit <= 0:
            raise ValueError("max_results must be a positive integer")
        return min(limit, _MAX_RESULTS_CAP)


@dataclass(frozen=True, slots=True)
class _SearchTarget:
    search_url: str
    keyword: str
    company: str
