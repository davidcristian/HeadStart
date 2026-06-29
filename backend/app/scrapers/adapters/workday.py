"""Workday job-board adapter.

Workday career sites expose a public Candidate Experience Service (CXS) API:
  POST https://{tenant}.{region}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs

Config / context:
  - `query_url`: careers board URL, a CXS jobs endpoint, or empty.
  - `config["tenant"]`: Workday tenant slug (required when query_url is empty).
  - `config["site"]`: board/site path segment (required when query_url is empty).
  - `config["region"]`: optional cluster host segment (e.g. `"wd5"`); inferred from
    the hostname when omitted.
  - `config["locale"]`: locale path prefix (default `"en-US"`).
  - `config["company"]`: display company name (defaults to tenant).
  - `config["page_size"]`: jobs per page (default 20, max 100).
  - `config["search_text"]`: optional keyword filter sent to the CXS API.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from app.scrapers.base import Scraper, register_scraper
from app.scrapers.types import JobPosting, ScrapeContext

_LOCALE_RE = re.compile(r"^[a-z]{2}-[A-Z]{2}$")
_HOST_WITH_REGION = re.compile(r"^([^.]+)\.(wd\d+)\.myworkdayjobs\.com$", re.IGNORECASE)
_HOST_PLAIN = re.compile(r"^([^.]+)\.myworkdayjobs\.com$", re.IGNORECASE)
_DEFAULT_PAGE_SIZE = 20
_MAX_PAGE_SIZE = 100


@register_scraper("workday")
class WorkdayScraper(Scraper):
    """Fetch postings from a Workday public career site via the CXS API."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        target = self._resolve(ctx)
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
                total = int(raw_total) if isinstance(raw_total, (int, float)) else len(jobs)
            if not jobs:
                break
            postings.extend(self._to_posting(job, target) for job in jobs if isinstance(job, dict))
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
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            raise ValueError("page_size must be a positive integer")
        size = int(raw)
        if size < 1:
            raise ValueError("page_size must be a positive integer")
        return min(size, _MAX_PAGE_SIZE)

    @staticmethod
    def _request_headers(target: _WorkdayTarget) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Referer": target.board_url,
        }

    @classmethod
    def _resolve(cls, ctx: ScrapeContext) -> _WorkdayTarget:
        config = ctx.config
        company = str(config.get("company") or config.get("tenant") or config.get("site") or "")
        locale = str(config.get("locale") or "en-US")
        tenant = str(config.get("tenant") or "")
        site = str(config.get("site") or "")
        region = str(config.get("region") or "") or None

        if ctx.query_url:
            return cls._from_query_url(ctx.query_url, company=company, locale=locale)

        if not tenant or not site:
            raise ValueError("workday scraper needs a query_url or config.tenant + config.site")
        host = cls._host(tenant, region)
        return _WorkdayTarget(
            tenant=tenant,
            site=site,
            region=region,
            locale=locale,
            company=company or tenant,
            host=host,
        )

    @classmethod
    def _from_query_url(cls, query_url: str, *, company: str, locale: str) -> _WorkdayTarget:
        parsed = urlparse(query_url)
        host = parsed.netloc.lower()
        tenant, region = cls._parse_host(host)
        parts = [part for part in parsed.path.split("/") if part]

        if len(parts) >= 4 and parts[0] == "wday" and parts[1] == "cxs":
            tenant = parts[2] or tenant
            site = parts[3]
            if not tenant or not site:
                raise ValueError("workday scraper could not determine tenant/site from query_url")
            return _WorkdayTarget(
                tenant=tenant,
                site=site,
                region=region,
                locale=locale,
                company=company or tenant,
                host=host,
            )

        if parts and _LOCALE_RE.match(parts[0]):
            locale = parts[0]
            parts = parts[1:]
        if not parts:
            raise ValueError("workday scraper could not determine site from query_url")
        site = parts[0]
        if not tenant:
            raise ValueError("workday scraper could not determine tenant from query_url")
        return _WorkdayTarget(
            tenant=tenant,
            site=site,
            region=region,
            locale=locale,
            company=company or tenant,
            host=host,
        )

    @staticmethod
    def _parse_host(host: str) -> tuple[str, str | None]:
        match = _HOST_WITH_REGION.match(host)
        if match:
            return match.group(1), match.group(2)
        match = _HOST_PLAIN.match(host)
        if match:
            return match.group(1), None
        raise ValueError("workday scraper query_url must be a *.myworkdayjobs.com URL")

    @staticmethod
    def _host(tenant: str, region: str | None) -> str:
        if region:
            return f"{tenant}.{region}.myworkdayjobs.com"
        return f"{tenant}.myworkdayjobs.com"

    @staticmethod
    def _to_posting(job: dict[str, Any], target: _WorkdayTarget) -> JobPosting:
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
            company=target.company,
            location=str(job.get("locationsText") or ""),
            url=url,
            raw=job,
        )


class _WorkdayTarget:
    """Resolved Workday tenant/site coordinates for one scrape."""

    def __init__(
        self,
        *,
        tenant: str,
        site: str,
        region: str | None,
        locale: str,
        company: str,
        host: str,
    ) -> None:
        self.tenant = tenant
        self.site = site
        self.region = region
        self.locale = locale
        self.company = company
        self.host = host

    @property
    def api_url(self) -> str:
        return f"https://{self.host}/wday/cxs/{self.tenant}/{self.site}/jobs"

    @property
    def board_url(self) -> str:
        return f"https://{self.host}/{self.locale}/{self.site}"

    def job_url(self, external_path: str) -> str:
        if not external_path:
            return self.board_url
        if external_path.startswith("/"):
            return f"https://{self.host}/{self.locale}/{self.site}{external_path}"
        return f"https://{self.host}/{self.locale}/{self.site}/{external_path}"
