"""iCIMS / Jibe Attract careers-site adapter.

Many iCIMS-backed employers (and Jibe Attract vanity domains) expose a public
JSON search endpoint used by the careers UI:

  GET {careers_base_url}/api/jobs?page=<n>&limit=<size>[&keywords=<q>]

Config / context:
  - ``query_url``: careers site root, ``/jobs`` path, or ``/api/jobs`` URL.
  - ``config["careers_base_url"]``: origin when ``query_url`` is empty.
  - ``config["company"]``: display name (falls back to each job's
    ``hiring_organization``).
  - ``config["keywords"]`` / ``q`` / ``search``: optional API keyword filter.
  - ``config["page_size"]``: jobs per page (default 50, max 100).
  - ``config["max_results"]``: cap across pages (default 1000).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlparse

from app.scrapers.base import Scraper, register_scraper
from app.scrapers.dates import parse_iso8601
from app.scrapers.numbers import coerce_count
from app.scrapers.types import JobPosting, ScrapeContext

_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 100
_DEFAULT_MAX_RESULTS = 1000
_MAX_RESULTS_CAP = 2000


@dataclass(frozen=True, slots=True)
class _SearchTarget:
    careers_base_url: str
    company: str
    keywords: str


@register_scraper("icims")
class IcimsScraper(Scraper):
    """Fetch postings from an iCIMS/Jibe Attract public ``/api/jobs`` endpoint."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        target = self._resolve(ctx)
        page_size = self._page_size(ctx.config)
        max_results = self._max_results(ctx.config)
        postings: list[JobPosting] = []
        seen: set[str] = set()
        total: int | None = None
        page = 1

        while len(postings) < max_results:
            data = self.http.get_json(
                self._list_url(
                    target.careers_base_url,
                    page=page,
                    limit=page_size,
                    keywords=target.keywords,
                )
            )
            if not isinstance(data, dict):
                raise ValueError("icims API returned unexpected payload (expected a JSON object)")
            jobs = data.get("jobs")
            if not isinstance(jobs, list):
                raise ValueError("icims API returned unexpected jobs field (expected a JSON array)")
            if total is None:
                total = coerce_count(data.get("totalCount", data.get("count")), len(jobs))
            if not jobs:
                break
            for raw in jobs:
                posting = self._to_posting(raw, target)
                if posting is None or posting.external_id in seen:
                    continue
                seen.add(posting.external_id)
                postings.append(posting)
                if len(postings) >= max_results:
                    break
            if len(jobs) < page_size:
                break
            if total is not None and page * page_size >= total:
                break
            page += 1

        return postings

    @classmethod
    def _resolve(cls, ctx: ScrapeContext) -> _SearchTarget:
        company = str(ctx.config.get("company") or "").strip()
        keywords = cls._keywords(ctx)
        base = str(ctx.config.get("careers_base_url") or "").strip()
        if ctx.query_url:
            base = cls._base_from_url(ctx.query_url.strip())
        if not base:
            raise ValueError("icims scraper needs a query_url or config.careers_base_url")
        return _SearchTarget(careers_base_url=base.rstrip("/"), company=company, keywords=keywords)

    @staticmethod
    def _base_from_url(query_url: str) -> str:
        parsed = urlparse(query_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("icims scraper query_url must be an http(s) careers site URL")
        return f"{parsed.scheme}://{parsed.netloc.lower()}"

    @staticmethod
    def _keywords(ctx: ScrapeContext) -> str:
        for key in ("keywords", "q", "search", "search_text"):
            raw = ctx.config.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
        filters = ctx.filters if isinstance(ctx.filters, dict) else {}
        for key in ("keywords", "q", "search"):
            raw = filters.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
        return ""

    @staticmethod
    def _list_url(base: str, *, page: int, limit: int, keywords: str) -> str:
        params: dict[str, str | int] = {"page": page, "limit": limit}
        if keywords:
            params["keywords"] = keywords
        return f"{base}/api/jobs?{urlencode(params)}"

    @staticmethod
    def _page_size(config: dict[str, Any]) -> int:
        raw = config.get("page_size", _DEFAULT_PAGE_SIZE)
        if not isinstance(raw, int | float) or isinstance(raw, bool):
            raise ValueError("page_size must be a positive integer")
        size = int(raw)
        if size <= 0:
            raise ValueError("page_size must be a positive integer")
        return min(size, _MAX_PAGE_SIZE)

    @staticmethod
    def _max_results(config: dict[str, Any]) -> int:
        raw = config.get("max_results", _DEFAULT_MAX_RESULTS)
        if not isinstance(raw, int | float) or isinstance(raw, bool):
            raise ValueError("max_results must be a positive integer")
        value = int(raw)
        if value <= 0:
            raise ValueError("max_results must be a positive integer")
        return min(value, _MAX_RESULTS_CAP)

    @classmethod
    def _to_posting(cls, raw: object, target: _SearchTarget) -> JobPosting | None:
        if not isinstance(raw, dict):
            return None
        data = raw.get("data")
        if not isinstance(data, dict):
            data = raw
        slug = str(data.get("slug") or data.get("req_id") or "").strip()
        title = str(data.get("title") or "").strip()
        if not slug or not title:
            return None
        company = target.company or str(data.get("hiring_organization") or "").strip() or "Unknown"
        location = cls._location(data)
        posted_at = parse_iso8601(data.get("posted_date") or data.get("create_date"))
        return JobPosting(
            external_id=slug,
            title=title,
            company=company,
            location=location,
            url=f"{target.careers_base_url}/jobs/{slug}",
            posted_at=posted_at,
            raw=data if isinstance(data, dict) else {},
        )

    @staticmethod
    def _location(data: dict[str, Any]) -> str:
        for key in ("full_location", "short_location", "location_name"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        parts = [
            str(data.get(key) or "").strip()
            for key in ("city", "state", "country")
            if str(data.get(key) or "").strip()
        ]
        return ", ".join(parts)
