"""SmartRecruiters job-board adapter.

SmartRecruiters exposes a public Postings API:
  GET https://api.smartrecruiters.com/v1/companies/{company_id}/postings

Config / context:
  - `query_url`: careers board URL, API URL, or empty.
  - `config["company_id"]`: company slug from
    `careers.smartrecruiters.com/{company_id}` (required when query_url is empty).
  - `config["company"]`: display company name (defaults to API payload or slug).
  - `config["page_size"]`: postings per page (default 100, max 100).
"""

from __future__ import annotations

import math
from typing import Any
from urllib.parse import urlencode, urlparse

from app.scrapers.base import Scraper, register_scraper
from app.scrapers.dates import parse_iso8601
from app.scrapers.types import JobPosting, ScrapeContext

SMARTRECRUITERS_API = "https://api.smartrecruiters.com/v1/companies/{company_id}/postings"
JOBS_BOARD = "https://jobs.smartrecruiters.com/{company_id}"
_DEFAULT_PAGE_SIZE = 100
_MAX_PAGE_SIZE = 100


@register_scraper("smartrecruiters")
class SmartRecruitersScraper(Scraper):
    """Fetch postings from a SmartRecruiters public careers board."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        company_id, company = self._resolve(ctx)
        page_size = self._page_size(ctx.config)
        postings: list[JobPosting] = []
        offset = 0
        total: int | None = None

        while total is None or offset < total:
            data = self.http.get_json(self._list_url(company_id, limit=page_size, offset=offset))
            if not isinstance(data, dict):
                raise ValueError(
                    "smartrecruiters API returned unexpected payload (expected a JSON object)"
                )
            content = data.get("content")
            if not isinstance(content, list):
                raise ValueError(
                    "smartrecruiters API returned unexpected content field (expected a JSON array)"
                )
            if total is None:
                total = self._coerce_count(data.get("totalFound"), len(content))
            if not content:
                break
            for job in content:
                if isinstance(job, dict):
                    postings.append(self._to_posting(job, company_id, company))
            offset += len(content)

        return postings

    def _resolve(self, ctx: ScrapeContext) -> tuple[str, str]:
        config = ctx.config
        company_id = str(config.get("company_id") or config.get("site") or "")
        company = str(config.get("company") or "")

        if ctx.query_url:
            resolved_id, resolved_company = self._parse_url(ctx.query_url, company_id)
            return resolved_id, company or resolved_company

        if not company_id:
            raise ValueError("smartrecruiters scraper needs a query_url or config.company_id")
        return company_id, company or company_id

    @classmethod
    def _parse_url(cls, query_url: str, fallback_company_id: str) -> tuple[str, str]:
        parsed = urlparse(query_url)
        host = parsed.netloc.lower()
        if host == "api.smartrecruiters.com":
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) >= 4 and parts[0] == "v1" and parts[1] == "companies":
                company_id = parts[2]
                company_name = cls._humanize_slug(company_id)
                return company_id, company_name
            raise ValueError("smartrecruiters scraper could not determine company_id from API URL")
        if host in {"careers.smartrecruiters.com", "jobs.smartrecruiters.com"}:
            parts = [part for part in parsed.path.split("/") if part]
            company_id = parts[0] if parts else fallback_company_id
            if not company_id:
                raise ValueError(
                    "smartrecruiters scraper could not determine company_id from board URL"
                )
            return company_id, cls._humanize_slug(company_id)
        raise ValueError(
            "smartrecruiters scraper query_url must be a careers board URL or Postings API URL"
        )

    @staticmethod
    def _list_url(company_id: str, *, limit: int, offset: int) -> str:
        base = SMARTRECRUITERS_API.format(company_id=company_id)
        query = urlencode({"limit": limit, "offset": offset})
        return f"{base}?{query}"

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
    def _coerce_count(raw: Any, default: int) -> int:
        """Coerce an untrusted total into a non-negative int.

        JSON ``Infinity`` / ``NaN`` (accepted by ``json.loads``) would raise on
        ``int()``; a bad total falls back to the page size so the scrape stops
        cleanly instead of crashing or looping forever.
        """
        if isinstance(raw, bool) or not isinstance(raw, int | float):
            return default
        if isinstance(raw, float) and not math.isfinite(raw):
            return default
        value = int(raw)
        return value if value >= 0 else default

    @staticmethod
    def _humanize_slug(slug: str) -> str:
        cleaned = slug.replace("-", " ").replace("_", " ").strip()
        return cleaned.title() if cleaned else slug

    @classmethod
    def _to_posting(cls, job: dict[str, Any], company_id: str, company: str) -> JobPosting:
        location = cls._location(job.get("location"))
        company_payload = job.get("company")
        display_company = company
        if isinstance(company_payload, dict):
            display_company = str(company_payload.get("name") or company or company_id)
        posted_at = parse_iso8601(job.get("releasedDate"))
        posting_id = str(job.get("id", ""))
        return JobPosting(
            external_id=posting_id,
            title=str(job.get("name", "")),
            company=display_company,
            location=location,
            url=f"{JOBS_BOARD.format(company_id=company_id)}/{posting_id}",
            posted_at=posted_at,
            raw=job,
        )

    @staticmethod
    def _location(raw: Any) -> str:
        if not isinstance(raw, dict):
            return ""
        full = raw.get("fullLocation")
        if isinstance(full, str) and full.strip():
            return full.strip()
        parts = [str(raw.get(key) or "").strip() for key in ("city", "region", "country")]
        return ", ".join(part for part in parts if part)
