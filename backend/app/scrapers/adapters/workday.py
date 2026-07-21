"""Workday job-board adapter.

Workday career sites expose a public Candidate Experience Service (CXS) API:
  POST https://{host}/wday/cxs/{tenant}/{site}/jobs

Hosts:
  - Classic: ``{tenant}.{region}.myworkdayjobs.com`` (or ``{tenant}.myworkdayjobs.com``)
  - Site: ``{region}.myworkdaysite.com`` with board path ``/recruiting/{tenant}/{site}``

Config / context:
  - `query_url`: careers board URL, a CXS jobs endpoint, or empty.
  - `config["tenant"]`: Workday tenant slug (required when query_url is empty).
  - `config["site"]`: board/site path segment (required when query_url is empty).
  - `config["region"]`: optional cluster host segment (e.g. `"wd5"`); required for
    ``host_kind=site``; inferred from the hostname when omitted on jobs hosts.
  - `config["host_kind"]`: ``"jobs"`` (default) or ``"site"`` for myworkdaysite.com.
  - `config["locale"]`: locale path prefix for jobs hosts (default `"en-US"`).
  - `config["company"]`: display company name (defaults to tenant).
  - `config["page_size"]`: jobs per page (default 20, max 100).
  - `config["search_text"]`: optional keyword filter sent to the CXS API.
"""

from __future__ import annotations

from typing import Any

from app.scrapers.adapters.workday_parse import (
    WorkdayBoard,
    board_from_url,
    build_host,
    normalize_host_kind,
)
from app.scrapers.base import Scraper, register_scraper
from app.scrapers.numbers import coerce_count
from app.scrapers.types import JobPosting, ScrapeContext

_DEFAULT_PAGE_SIZE = 20
_MAX_PAGE_SIZE = 100


@register_scraper("workday")
class WorkdayScraper(Scraper):
    """Fetch postings from a Workday public career site via the CXS API."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        target = self._resolve(ctx)
        company = target_company(ctx, target)
        search_text = self._search_text(ctx)
        page_size = self._page_size(ctx.config)
        postings: list[JobPosting] = []
        offset = 0
        total: int | None = None

        while total is None or offset < total:
            payload = {
                "appliedFacets": {},
                "limit": page_size,
                "offset": offset,
                "searchText": search_text,
            }
            data = self.http.post_json(
                target.api_url,
                json=payload,
                headers=self._request_headers(target),
            )
            if not isinstance(data, dict):
                raise ValueError("workday API returned unexpected payload (expected a JSON object)")
            jobs = data.get("jobPostings")
            if not isinstance(jobs, list):
                raise ValueError(
                    "workday API returned unexpected jobPostings field (expected a JSON array)"
                )
            if total is None:
                raw_total = data.get("total", len(jobs))
                total = coerce_count(raw_total, len(jobs))
            if not jobs:
                break
            postings.extend(
                self._to_posting(job, target, company=company)
                for job in jobs
                if isinstance(job, dict)
            )
            offset += len(jobs)

        return postings

    @staticmethod
    def _search_text(ctx: ScrapeContext) -> str:
        for key in ("search_text", "keywords", "q"):
            value = ctx.config.get(key)
            if value:
                return str(value)
        keywords = ctx.filters.get("keywords") or ctx.filters.get("keywords_include")
        if isinstance(keywords, list) and keywords:
            return " ".join(str(k) for k in keywords)
        if isinstance(keywords, str) and keywords:
            return keywords
        return ""

    @staticmethod
    def _page_size(config: dict[str, Any]) -> int:
        raw = config.get("page_size", _DEFAULT_PAGE_SIZE)
        if not isinstance(raw, int | float) or isinstance(raw, bool):
            raise ValueError("page_size must be a positive integer")
        size = int(raw)
        if size < 1:
            raise ValueError("page_size must be a positive integer")
        return min(size, _MAX_PAGE_SIZE)

    @staticmethod
    def _request_headers(target: WorkdayBoard) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Referer": target.board_url,
        }

    @classmethod
    def _resolve(cls, ctx: ScrapeContext) -> WorkdayBoard:
        config = ctx.config
        locale = str(config.get("locale") or "en-US")
        tenant = str(config.get("tenant") or "")
        site = str(config.get("site") or "")
        region = str(config.get("region") or "") or None
        host_kind = normalize_host_kind(config.get("host_kind"))

        if ctx.query_url:
            return board_from_url(ctx.query_url, locale=locale)

        if not tenant or not site:
            raise ValueError("workday scraper needs a query_url or config.tenant + config.site")
        return WorkdayBoard(
            tenant=tenant,
            site=site,
            region=region,
            locale=locale,
            host=build_host(tenant, region, host_kind),
            host_kind=host_kind,
        )

    @staticmethod
    def _to_posting(job: dict[str, Any], target: WorkdayBoard, *, company: str) -> JobPosting:
        external_path = str(job.get("externalPath") or "")
        url = target.job_url(external_path)
        bullet_fields = job.get("bulletFields")
        external_id = ""
        if isinstance(bullet_fields, list) and bullet_fields:
            external_id = str(bullet_fields[0])
        if not external_id:
            external_id = external_path or str(job.get("title", ""))
        return JobPosting(
            external_id=external_id,
            title=str(job.get("title", "")),
            company=company,
            location=str(job.get("locationsText") or ""),
            url=url,
            raw=job,
        )


def target_company(ctx: ScrapeContext, target: WorkdayBoard) -> str:
    """Display company from config, falling back to the resolved tenant."""
    config = ctx.config
    return str(config.get("company") or config.get("tenant") or target.tenant or target.site)
