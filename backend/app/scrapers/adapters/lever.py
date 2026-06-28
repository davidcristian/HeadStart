"""Lever job-board adapter.

Lever exposes a public Postings API:
  https://api.lever.co/v0/postings/<site>?mode=json

Config / context:
  - `query_url`: full API URL, a jobs.lever.co board URL, or empty.
  - `config["site"]`: Lever site slug (required when query_url is empty or a
    careers page URL).
  - `config["company"]`: display company name (defaults to site).
  - `config["region"]`: optional `"eu"` for the EU API host.
"""

from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from app.scrapers.base import Scraper, register_scraper
from app.scrapers.types import JobPosting, ScrapeContext

LEVER_API = {
    "global": "https://api.lever.co/v0/postings/{site}",
    "eu": "https://api.eu.lever.co/v0/postings/{site}",
}


@register_scraper("lever")
class LeverScraper(Scraper):
    """Fetch postings from a Lever public job board."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        url, company = self._resolve(ctx)
        data = self.http.get_json(url)
        if not isinstance(data, list):
            raise ValueError("lever API returned unexpected payload (expected a JSON array)")
        return [self._to_posting(job, company) for job in data]

    def _resolve(self, ctx: ScrapeContext) -> tuple[str, str]:
        config = ctx.config
        region = str(config.get("region", "global")).lower()
        site = str(config.get("site") or "")
        company = str(config.get("company") or site or "")

        if ctx.query_url:
            url = self._normalize_url(ctx.query_url, site=site, region=region)
            return url, company

        if not site:
            raise ValueError("lever scraper needs a query_url or config.site")
        return self._api_url(site, region), company

    @classmethod
    def _normalize_url(cls, query_url: str, *, site: str, region: str) -> str:
        parsed = urlparse(query_url)
        host = parsed.netloc.lower()
        if host.startswith("jobs.") and host.endswith(".lever.co"):
            slug = parsed.path.strip("/").split("/")[0] or site
            if not slug:
                raise ValueError("lever scraper could not determine site from query_url")
            return cls._api_url(slug, region)
        return cls._with_json_mode(query_url)

    @staticmethod
    def _api_url(site: str, region: str) -> str:
        base = LEVER_API.get(region, LEVER_API["global"])
        return f"{base.format(site=site)}?mode=json"

    @staticmethod
    def _with_json_mode(url: str) -> str:
        parsed = urlparse(url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        if "mode" not in params:
            params["mode"] = ["json"]
        query = urlencode({k: v[0] for k, v in params.items()})
        return urlunparse(parsed._replace(query=query))

    @staticmethod
    def _to_posting(job: dict[str, Any], company: str) -> JobPosting:
        categories = job.get("categories") or {}
        location = ""
        if isinstance(categories, dict):
            location = str(categories.get("location") or "")
            if not location:
                all_locs = categories.get("allLocations")
                if isinstance(all_locs, list) and all_locs:
                    location = str(all_locs[0])
        posted_at = None
        created = job.get("createdAt")
        if isinstance(created, (int, float)):
            posted_at = datetime.fromtimestamp(created / 1000, tz=UTC)
        return JobPosting(
            external_id=str(job.get("id", "")),
            title=str(job.get("text", "")),
            company=company,
            location=location,
            url=str(job.get("hostedUrl", "")),
            posted_at=posted_at,
            raw=job,
        )
