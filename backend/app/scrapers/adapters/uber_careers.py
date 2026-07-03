"""Uber Careers job-search adapter.

Uber's careers site exposes a first-party JSON search API:
  POST https://www.uber.com/api/loadSearchJobsResults?localeCode=<locale>

Config / context:
  - `query_url`: careers list URL on uber.com (optional).
  - `config["locale"]`: API locale code (default ``en``).
  - `config["careers_locale_path"]`: path prefix for job URLs (default ``us/en``).
  - `config["q"]` / `config["search"]` / `config["search_text"]`: client-side keyword filter.
  - `config["country"]`: optional ISO country filter sent to the API (e.g. ``USA``).
  - `config["company"]`: display company name (defaults to ``Uber``).
  - `config["page_size"]`: jobs per request (default 100, max 100).
  - `config["max_results"]`: cap across pages (default 500).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from app.scrapers.adapters.uber_careers_parse import parse_search_response
from app.scrapers.base import Scraper, register_scraper
from app.scrapers.types import JobPosting, ScrapeContext

_API_PATH = "/api/loadSearchJobsResults"
_DEFAULT_LOCALE = "en"
_DEFAULT_CAREERS_LOCALE_PATH = "us/en"
_DEFAULT_COMPANY = "Uber"
_DEFAULT_PAGE_SIZE = 100
_MAX_PAGE_SIZE = 100
_DEFAULT_MAX_RESULTS = 500
_MAX_RESULTS_CAP = 1000
_HOST_RE = re.compile(r"^(?:www\.)?uber\.com$", re.IGNORECASE)
_CAREERS_PATH_RE = re.compile(r"^/(?:[a-z]{2}/[a-z]{2}/)?careers(?:/|$)", re.IGNORECASE)


@register_scraper("uber_careers")
class UberCareersScraper(Scraper):
    """Fetch postings from Uber Careers via the public search API."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        target = self._resolve(ctx)
        page_size = self._page_size(ctx.config)
        max_results = self._max_results(ctx.config)
        postings: list[JobPosting] = []
        seen: set[str] = set()
        total: int | None = None
        page = 0

        while len(postings) < max_results:
            payload = self.http.post_json(
                target.api_url,
                json=self._request_body(target, page=page, page_size=page_size),
                headers=self._api_headers(target.referer_url),
            )
            if not isinstance(payload, dict):
                raise ValueError(
                    "uber_careers API returned unexpected payload (expected a JSON object)"
                )
            page_jobs, page_total = parse_search_response(
                payload,
                company=target.company,
                careers_base_url=target.careers_base_url,
            )
            if total is None:
                total = page_total
            if not page_jobs:
                break
            for job in page_jobs:
                if job.external_id in seen:
                    continue
                if target.keyword and not self._matches_keyword(job, target.keyword):
                    continue
                seen.add(job.external_id)
                postings.append(job)
                if len(postings) >= max_results:
                    break
            page += 1
            if total is not None and page * page_size >= total:
                break
            if len(page_jobs) < page_size:
                break

        return postings

    @staticmethod
    def _resolve(ctx: ScrapeContext) -> _SearchTarget:
        company = str(ctx.config.get("company") or _DEFAULT_COMPANY)
        locale = str(ctx.config.get("locale") or _DEFAULT_LOCALE)
        careers_locale_path = str(
            ctx.config.get("careers_locale_path") or _DEFAULT_CAREERS_LOCALE_PATH
        ).strip("/")
        keyword = UberCareersScraper._keyword(ctx)
        country = UberCareersScraper._country(ctx)

        if ctx.query_url:
            parsed = urlparse(ctx.query_url.strip())
            host = parsed.netloc.lower()
            if not _HOST_RE.match(host):
                raise ValueError("uber_careers scraper requires an uber.com careers URL")
            if not _CAREERS_PATH_RE.match(parsed.path):
                raise ValueError("uber_careers query_url must point at the careers section")
            path_parts = [part for part in parsed.path.split("/") if part]
            if len(path_parts) >= 2 and len(path_parts[0]) == 2 and len(path_parts[1]) == 2:
                careers_locale_path = f"{path_parts[0]}/{path_parts[1]}"

        careers_base_url = f"https://www.uber.com/{careers_locale_path}/careers/list"
        referer_url = f"{careers_base_url}/"
        api_url = f"https://www.uber.com{_API_PATH}?localeCode={locale}"
        return _SearchTarget(
            api_url=api_url,
            referer_url=referer_url,
            careers_base_url=careers_base_url,
            company=company,
            keyword=keyword,
            country=country,
        )

    @staticmethod
    def _request_body(target: _SearchTarget, *, page: int, page_size: int) -> dict[str, Any]:
        location_filters: list[dict[str, str]] = []
        if target.country:
            location_filters.append({"country": target.country})
        return {
            "limit": page_size,
            "page": page,
            "params": {
                "department": [],
                "lineOfBusinessName": [],
                "location": location_filters,
                "programAndPlatform": [],
                "team": [],
            },
        }

    @staticmethod
    def _api_headers(referer_url: str) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Referer": referer_url,
            "x-csrf-token": "x",
            "x-uber-sites-page-edge-cache-enabled": "true",
        }

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
    def _country(ctx: ScrapeContext) -> str:
        for key in ("country", "location_country"):
            value = ctx.config.get(key)
            if value:
                return str(value).strip().upper()
        location = ctx.filters.get("location")
        if location:
            return str(location).strip().upper()
        return ""

    @staticmethod
    def _matches_keyword(job: JobPosting, keyword: str) -> bool:
        haystack = " ".join(
            part
            for part in (
                job.title,
                job.location,
                str(job.raw.get("department") or ""),
                str(job.raw.get("team") or ""),
                str(job.raw.get("programAndPlatform") or ""),
            )
            if part
        ).lower()
        return keyword in haystack

    @staticmethod
    def _page_size(config: dict[str, Any]) -> int:
        raw = config.get("page_size", _DEFAULT_PAGE_SIZE)
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            raise ValueError("page_size must be a positive integer")
        limit = int(raw)
        if limit <= 0:
            raise ValueError("page_size must be a positive integer")
        return min(limit, _MAX_PAGE_SIZE)

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
    api_url: str
    referer_url: str
    careers_base_url: str
    company: str
    keyword: str
    country: str
