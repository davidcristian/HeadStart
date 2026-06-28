"""Greenhouse job-board adapter.

Many companies host their careers on Greenhouse, which exposes a clean public
JSON API:  https://boards-api.greenhouse.io/v1/boards/<token>/jobs?content=true

Config / context:
  - `query_url`: full jobs API URL (optional). If absent, it is built from
    `config["board_token"]`.
  - `config["company"]`: display company name (defaults to the board token).
"""

from typing import Any

from app.scrapers.base import Scraper, register_scraper
from app.scrapers.types import JobPosting, ScrapeContext

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"


@register_scraper("greenhouse")
class GreenhouseScraper(Scraper):
    """Fetch postings from a Greenhouse public job board."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        url = ctx.query_url or self._build_url(ctx.config)
        company = str(ctx.config.get("company") or ctx.config.get("board_token") or "")
        data = self.http.get_json(url)
        return [self._to_posting(job, company) for job in data.get("jobs", [])]

    @staticmethod
    def _build_url(config: dict[str, Any]) -> str:
        token = config.get("board_token")
        if not token:
            raise ValueError("greenhouse scraper needs a query_url or config.board_token")
        return GREENHOUSE_API.format(token=token)

    @staticmethod
    def _to_posting(job: dict[str, Any], company: str) -> JobPosting:
        location = ""
        loc = job.get("location")
        if isinstance(loc, dict):
            location = str(loc.get("name", ""))
        return JobPosting(
            external_id=str(job.get("id", "")),
            title=str(job.get("title", "")),
            company=company,
            location=location,
            url=str(job.get("absolute_url", "")),
            raw=job,
        )
