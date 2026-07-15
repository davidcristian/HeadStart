"""Amazon Jobs (amazon.jobs) search adapter.

Amazon's careers site exposes a public JSON search endpoint:
  GET https://www.amazon.jobs/<locale>/search.json

Config / context:
  - `query_url`: careers search URL or the search.json API URL.
  - `config["locale"]`: path locale (default ``en``).
  - `config["q"]` / `config["base_query"]` / `config["search_text"]`: keyword filter.
  - `config["location"]` / `config["loc_query"]`: location text filter.
  - `config["country"]`: ISO 3166-1 alpha-3 country code (e.g. ``USA``).
  - `config["region"]`: state/province abbreviation filter.
  - `config["city"]`: city filter.
  - `config["company"]`: display company name (defaults to ``Amazon``).
  - `config["page_size"]` / `config["result_limit"]`: jobs per request (default 100, max 100).
  - `config["max_results"]`: cap across pages (default 200).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from app.scrapers.base import Scraper, register_scraper
from app.scrapers.numbers import coerce_count
from app.scrapers.types import JobPosting, ScrapeContext

_ORIGIN = "https://www.amazon.jobs"
_DEFAULT_LOCALE = "en"
_DEFAULT_COMPANY = "Amazon"
_DEFAULT_PAGE_SIZE = 100
_MAX_PAGE_SIZE = 100
_DEFAULT_MAX_RESULTS = 200
_MAX_RESULTS_CAP = 500
_HOST_RE = re.compile(r"^(?:www\.)?amazon\.jobs$", re.IGNORECASE)
_LOCALE_PATH_RE = re.compile(r"^/([a-z]{2})(?:/|$)", re.IGNORECASE)
_POSTED_DATE_RE = re.compile(r"^([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})$")


@register_scraper("amazon_jobs")
class AmazonJobsScraper(Scraper):
    """Fetch postings from amazon.jobs via the public search.json API."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        target = self._resolve(ctx)
        page_size = self._page_size(ctx.config)
        max_results = self._max_results(ctx.config)
        postings: list[JobPosting] = []
        seen: set[str] = set()
        offset = 0
        total: int | None = None

        while len(postings) < max_results:
            params = {
                "offset": offset,
                "result_limit": page_size,
                "sort": "relevant",
            }
            if target.base_query:
                params["base_query"] = target.base_query
            if target.loc_query:
                params["loc_query"] = target.loc_query
            if target.country:
                params["country"] = target.country
            if target.region:
                params["region"] = target.region
            if target.city:
                params["city"] = target.city

            api_path = f"/{target.locale}/search.json"
            data = self.http.get_json(f"{_ORIGIN}{api_path}?{urlencode(params)}")
            jobs, count = self._parse_response(data)
            if total is None:
                total = count
            if not jobs:
                break
            for job in jobs:
                posting = self._to_posting(job, company=target.company)
                if posting.external_id in seen:
                    continue
                seen.add(posting.external_id)
                postings.append(posting)
                if len(postings) >= max_results:
                    break
            offset += len(jobs)
            if total is not None and offset >= total:
                break
            if len(jobs) < page_size:
                break

        return postings

    @staticmethod
    def _resolve(ctx: ScrapeContext) -> _SearchTarget:
        company = str(ctx.config.get("company") or _DEFAULT_COMPANY)
        locale = str(ctx.config.get("locale") or _DEFAULT_LOCALE)
        base_query = AmazonJobsScraper._keyword(ctx)
        loc_query = AmazonJobsScraper._location(ctx)
        country = AmazonJobsScraper._config_str(ctx.config, "country")
        region = AmazonJobsScraper._config_str(ctx.config, "region")
        city = AmazonJobsScraper._config_str(ctx.config, "city")

        if ctx.query_url:
            parsed = urlparse(ctx.query_url.strip())
            host = parsed.netloc.lower()
            if not _HOST_RE.match(host):
                raise ValueError("amazon_jobs scraper requires an amazon.jobs URL")

            path_locale = _LOCALE_PATH_RE.match(parsed.path)
            if path_locale:
                locale = path_locale.group(1)

            path = parsed.path
            if path.endswith("/search.json") or "/search" in path or "/jobs/" in path:
                params = parse_qs(parsed.query, keep_blank_values=True)
                base_query = AmazonJobsScraper._first_param(params, "base_query", base_query)
                loc_query = AmazonJobsScraper._first_param(params, "loc_query", loc_query)
                country = AmazonJobsScraper._first_param(params, "country", country)
                region = AmazonJobsScraper._first_param(params, "region", region)
                city = AmazonJobsScraper._first_param(params, "city", city)

        return _SearchTarget(
            locale=locale,
            base_query=base_query,
            loc_query=loc_query,
            country=country,
            region=region,
            city=city,
            company=company,
        )

    @staticmethod
    def _keyword(ctx: ScrapeContext) -> str:
        for key in ("base_query", "q", "search_text", "keywords"):
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
        for key in ("loc_query", "location", "l"):
            value = ctx.config.get(key)
            if value:
                return str(value).strip()
        value = ctx.filters.get("location")
        return str(value).strip() if value else ""

    @staticmethod
    def _config_str(config: dict[str, Any], key: str) -> str:
        value = config.get(key)
        return str(value).strip() if value else ""

    @staticmethod
    def _first_param(params: dict[str, list[str]], key: str, fallback: str) -> str:
        values = params.get(key)
        if values and values[0]:
            return values[0].strip()
        return fallback

    @staticmethod
    def _page_size(config: dict[str, Any]) -> int:
        raw = config.get("page_size", config.get("result_limit", _DEFAULT_PAGE_SIZE))
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
            raise ValueError("amazon_jobs API returned unexpected payload (expected object)")
        jobs = data.get("jobs")
        if not isinstance(jobs, list):
            raise ValueError("amazon_jobs API returned unexpected jobs field (expected array)")
        raw_hits = data.get("hits", len(jobs))
        count = coerce_count(raw_hits, len(jobs))
        return [job for job in jobs if isinstance(job, dict)], count

    @staticmethod
    def _to_posting(job: dict[str, Any], *, company: str) -> JobPosting:
        external_id = str(job.get("id_icims") or job.get("id") or "").strip()
        if not external_id:
            raise ValueError("amazon_jobs job is missing id")
        title = str(job.get("title") or "").strip()
        location = AmazonJobsScraper._format_location(job)
        url = AmazonJobsScraper._job_url(job)
        posted_at = AmazonJobsScraper._posted_at(job)
        display_company = str(job.get("company_name") or company).strip() or company
        return JobPosting(
            external_id=external_id,
            title=title,
            company=display_company,
            location=location,
            url=url,
            posted_at=posted_at,
            raw=job,
        )

    @staticmethod
    def _format_location(job: dict[str, Any]) -> str:
        normalized = str(job.get("normalized_location") or "").strip()
        if normalized:
            return normalized
        return str(job.get("location") or "").strip()

    @staticmethod
    def _job_url(job: dict[str, Any]) -> str:
        job_path = str(job.get("job_path") or "").strip()
        if not job_path:
            external_id = job.get("id_icims") or job.get("id")
            if external_id:
                job_path = f"/en/jobs/{external_id}"
        if job_path.startswith("http://") or job_path.startswith("https://"):
            return job_path
        if job_path.startswith("/"):
            return f"{_ORIGIN}{job_path}"
        return f"{_ORIGIN}/{job_path}" if job_path else _ORIGIN

    @staticmethod
    def _posted_at(job: dict[str, Any]) -> datetime | None:
        raw = str(job.get("posted_date") or "").strip()
        if not raw:
            return None
        normalized = re.sub(r"\s+", " ", raw)
        match = _POSTED_DATE_RE.match(normalized)
        if not match:
            return None
        try:
            parsed = datetime.strptime(normalized, "%B %d, %Y")
        except ValueError:
            return None
        return parsed.replace(tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class _SearchTarget:
    locale: str
    base_query: str
    loc_query: str
    country: str
    region: str
    city: str
    company: str
