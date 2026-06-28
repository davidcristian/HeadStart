"""Ashby job-board adapter.

Ashby exposes a public Postings API:
  https://api.ashbyhq.com/posting-api/job-board/<board>

Config / context:
  - `query_url`: full API URL, a jobs.ashbyhq.com board URL, or empty.
  - `config["board"]`: Ashby jobs page name (required when query_url is empty or a
    careers page URL).
  - `config["company"]`: display company name (defaults to board).
  - `config["include_compensation"]`: optional bool; adds salary data to the API
    response when true (default false).
"""

from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from app.scrapers.base import Scraper, register_scraper
from app.scrapers.types import JobPosting, ScrapeContext

ASHBY_API = "https://api.ashbyhq.com/posting-api/job-board/{board}"


@register_scraper("ashby")
class AshbyScraper(Scraper):
    """Fetch postings from an Ashby public job board."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        url, company = self._resolve(ctx)
        data = self.http.get_json(url)
        if not isinstance(data, dict):
            raise ValueError("ashby API returned unexpected payload (expected a JSON object)")
        jobs = data.get("jobs")
        if not isinstance(jobs, list):
            raise ValueError("ashby API returned unexpected jobs field (expected a JSON array)")
        listed = [job for job in jobs if isinstance(job, dict) and job.get("isListed", True)]
        return [self._to_posting(job, company) for job in listed]

    def _resolve(self, ctx: ScrapeContext) -> tuple[str, str]:
        config = ctx.config
        board = str(config.get("board") or config.get("site") or "")
        company = str(config.get("company") or board or "")
        include_compensation = bool(config.get("include_compensation", False))

        if ctx.query_url:
            url = self._normalize_url(
                ctx.query_url,
                board=board,
                include_compensation=include_compensation,
            )
            return url, company

        if not board:
            raise ValueError("ashby scraper needs a query_url or config.board")
        return self._api_url(board, include_compensation), company

    @classmethod
    def _normalize_url(
        cls,
        query_url: str,
        *,
        board: str,
        include_compensation: bool,
    ) -> str:
        parsed = urlparse(query_url)
        host = parsed.netloc.lower()
        if host == "jobs.ashbyhq.com":
            slug = parsed.path.strip("/").split("/")[0] or board
            if not slug:
                raise ValueError("ashby scraper could not determine board from query_url")
            return cls._api_url(slug, include_compensation)
        if "posting-api/job-board" in parsed.path:
            return cls._with_compensation(query_url, include_compensation)
        raise ValueError("ashby scraper query_url must be an API URL or jobs.ashbyhq.com board URL")

    @staticmethod
    def _api_url(board: str, include_compensation: bool) -> str:
        url = ASHBY_API.format(board=board)
        if include_compensation:
            return f"{url}?includeCompensation=true"
        return url

    @staticmethod
    def _with_compensation(url: str, include_compensation: bool) -> str:
        if not include_compensation:
            return url
        parsed = urlparse(url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        if "includeCompensation" not in params:
            params["includeCompensation"] = ["true"]
        query = urlencode({k: v[0] for k, v in params.items()})
        return urlunparse(parsed._replace(query=query))

    @staticmethod
    def _to_posting(job: dict[str, Any], company: str) -> JobPosting:
        location = str(job.get("location") or "")
        if not location and isinstance(job.get("secondaryLocations"), list):
            secondary = job["secondaryLocations"]
            if secondary and isinstance(secondary[0], dict):
                location = str(secondary[0].get("location") or "")
        posted_at = None
        published = job.get("publishedAt")
        if isinstance(published, str) and published:
            posted_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
        return JobPosting(
            external_id=str(job.get("id", "")),
            title=str(job.get("title", "")),
            company=company,
            location=location,
            url=str(job.get("jobUrl", "")),
            posted_at=posted_at,
            raw=job,
        )
