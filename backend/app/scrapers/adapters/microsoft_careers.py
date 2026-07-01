"""Microsoft Careers job-search adapter (Eightfold PCSX API).

Microsoft's apply portal exposes a public JSON search endpoint:
  GET https://apply.careers.microsoft.com/api/pcsx/search

Config / context:
  - `query_url`: careers board URL or the PCSX search API URL.
  - `config["domain"]`: Eightfold domain slug (default ``microsoft.com``).
  - `config["q"]` / `config["search_text"]`: keyword filter.
  - `config["location"]`: optional location filter.
  - `config["company"]`: display company name (defaults to ``Microsoft``).
  - `config["page_size"]`: jobs per request (default 20, max 50).
  - `config["max_results"]`: cap across pages (default 200).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from app.scrapers.base import Scraper, register_scraper
from app.scrapers.types import JobPosting, ScrapeContext

_ORIGIN = "https://apply.careers.microsoft.com"
_API_PATH = "/api/pcsx/search"
_CAREERS_PATH = "/careers"
_DEFAULT_DOMAIN = "microsoft.com"
_DEFAULT_COMPANY = "Microsoft"
_DEFAULT_PAGE_SIZE = 20
_MAX_PAGE_SIZE = 50
_DEFAULT_MAX_RESULTS = 200
_MAX_RESULTS_CAP = 500
_HOST_RE = re.compile(
    r"^(?:apply\.)?careers\.microsoft\.com$",
    re.IGNORECASE,
)


@register_scraper("microsoft_careers")
class MicrosoftCareersScraper(Scraper):
    """Fetch postings from Microsoft Careers via the public PCSX search API."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        target = self._resolve(ctx)
        page_size = self._page_size(ctx.config)
        max_results = self._max_results(ctx.config)
        postings: list[JobPosting] = []
        seen: set[str] = set()
        start = 0
        total: int | None = None

        while len(postings) < max_results:
            params = {
                "domain": target.domain,
                "query": target.query,
                "start": start,
                "num": page_size,
            }
            if target.location:
                params["location"] = target.location
            data = self.http.get_json(f"{_ORIGIN}{_API_PATH}?{urlencode(params)}")
            positions, count = self._parse_response(data)
            if total is None:
                total = count
            if not positions:
                break
            for position in positions:
                posting = self._to_posting(position, company=target.company)
                if posting.external_id in seen:
                    continue
                seen.add(posting.external_id)
                postings.append(posting)
                if len(postings) >= max_results:
                    break
            start += len(positions)
            if total is not None and start >= total:
                break
            if len(positions) < page_size:
                break

        return postings

    @staticmethod
    def _resolve(ctx: ScrapeContext) -> _SearchTarget:
        company = str(ctx.config.get("company") or _DEFAULT_COMPANY)
        domain = str(ctx.config.get("domain") or _DEFAULT_DOMAIN)
        query = MicrosoftCareersScraper._keyword(ctx)
        location = MicrosoftCareersScraper._location(ctx)

        if ctx.query_url:
            parsed = urlparse(ctx.query_url.strip())
            host = parsed.netloc.lower()
            if parsed.path.startswith(_API_PATH):
                params = parse_qs(parsed.query, keep_blank_values=True)
                domain = (params.get("domain") or [domain])[0] or domain
                query = (params.get("query") or params.get("q") or [query])[0] or query
                location = (params.get("location") or [location])[0] or location
            elif _HOST_RE.match(host):
                params = parse_qs(parsed.query, keep_blank_values=True)
                query = (params.get("q") or params.get("query") or [query])[0] or query
                location = (params.get("location") or params.get("l") or [location])[0] or location
            else:
                raise ValueError(
                    "microsoft_careers scraper requires an apply.careers.microsoft.com URL"
                )

        return _SearchTarget(domain=domain, query=query, location=location, company=company)

    @staticmethod
    def _keyword(ctx: ScrapeContext) -> str:
        for key in ("q", "search_text", "keywords", "query"):
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
    def _page_size(config: dict[str, Any]) -> int:
        raw = config.get("page_size", _DEFAULT_PAGE_SIZE)
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            raise ValueError("page_size must be a positive integer")
        size = int(raw)
        if size <= 0:
            raise ValueError("page_size must be a positive integer")
        return min(size, _MAX_PAGE_SIZE)

    @staticmethod
    def _max_results(config: dict[str, Any]) -> int:
        raw = config.get("max_results", _DEFAULT_MAX_RESULTS)
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            raise ValueError("max_results must be a positive integer")
        limit = int(raw)
        if limit <= 0:
            raise ValueError("max_results must be a positive integer")
        return min(limit, _MAX_RESULTS_CAP)

    @staticmethod
    def _parse_response(data: Any) -> tuple[list[dict[str, Any]], int]:
        if not isinstance(data, dict):
            raise ValueError("microsoft_careers API returned unexpected payload (expected object)")
        payload = data.get("data")
        if not isinstance(payload, dict):
            raise ValueError(
                "microsoft_careers API returned unexpected data field (expected object)"
            )
        positions = payload.get("positions")
        if not isinstance(positions, list):
            raise ValueError(
                "microsoft_careers API returned unexpected positions field (expected array)"
            )
        raw_count = payload.get("count", len(positions))
        count = int(raw_count) if isinstance(raw_count, (int, float)) else len(positions)
        jobs = [job for job in positions if isinstance(job, dict)]
        return jobs, count

    @staticmethod
    def _to_posting(job: dict[str, Any], *, company: str) -> JobPosting:
        external_id = str(job.get("id") or job.get("displayJobId") or job.get("atsJobId") or "")
        if not external_id:
            raise ValueError("microsoft_careers job is missing id")
        title = str(job.get("name") or "").strip()
        location = MicrosoftCareersScraper._format_location(job)
        url = MicrosoftCareersScraper._job_url(job)
        posted_at = MicrosoftCareersScraper._posted_at(job)
        return JobPosting(
            external_id=external_id,
            title=title,
            company=company,
            location=location,
            url=url,
            posted_at=posted_at,
            raw=job,
        )

    @staticmethod
    def _format_location(job: dict[str, Any]) -> str:
        standardized = job.get("standardizedLocations")
        if isinstance(standardized, list) and standardized:
            return "; ".join(str(item) for item in standardized if item)
        locations = job.get("locations")
        if isinstance(locations, list) and locations:
            return "; ".join(str(item) for item in locations if item)
        return ""

    @staticmethod
    def _job_url(job: dict[str, Any]) -> str:
        position_url = str(job.get("positionUrl") or "").strip()
        if not position_url:
            job_id = job.get("id")
            if job_id:
                position_url = f"/careers/job/{job_id}"
        if position_url.startswith("http://") or position_url.startswith("https://"):
            return position_url
        if position_url.startswith("/"):
            return f"{_ORIGIN}{position_url}"
        return f"{_ORIGIN}/{position_url}" if position_url else _ORIGIN + _CAREERS_PATH

    @staticmethod
    def _posted_at(job: dict[str, Any]) -> datetime | None:
        raw = job.get("postedTs")
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            return None
        return datetime.fromtimestamp(float(raw), tz=UTC)


@dataclass(frozen=True, slots=True)
class _SearchTarget:
    domain: str
    query: str
    location: str
    company: str
