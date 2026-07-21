"""Workday tenant/site resolution for the apply adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from app.scrapers.adapters.workday_parse import (
    HOST_KIND_JOBS,
    WorkdayBoard,
    board_from_url,
    build_host,
    extract_job_path,
    normalize_host_kind,
    try_parse_host,
)


@dataclass(frozen=True)
class WorkdayTarget:
    """Resolved Workday tenant/site coordinates."""

    tenant: str
    site: str
    region: str | None
    locale: str
    company: str
    host: str
    host_kind: str = HOST_KIND_JOBS

    @property
    def board_url(self) -> str:
        return WorkdayBoard(
            tenant=self.tenant,
            site=self.site,
            region=self.region,
            locale=self.locale,
            host=self.host,
            host_kind=self.host_kind,
        ).board_url

    def job_page_url(self, job_path: str) -> str:
        cleaned = str(job_path).strip("/")
        board = WorkdayBoard(
            tenant=self.tenant,
            site=self.site,
            region=self.region,
            locale=self.locale,
            host=self.host,
            host_kind=self.host_kind,
        )
        return board.job_url(f"/job/{cleaned}")

    def apply_referer(self, job_path: str) -> str:
        return f"{self.job_page_url(job_path)}/apply"

    def api_base(self) -> str:
        return f"https://{self.host}/wday/cxs/{self.tenant}"


def resolve_target(config: dict[str, Any], job_url: str) -> WorkdayTarget | None:
    """Tenant/site coordinates from config or a careers job URL."""
    company = str(config.get("company") or config.get("tenant") or config.get("site") or "")
    locale = str(config.get("locale") or "en-US")
    tenant = str(config.get("tenant") or "")
    site = str(config.get("site") or "")
    region = str(config.get("region") or "") or None
    host_kind = normalize_host_kind(config.get("host_kind"))

    if job_url:
        try:
            return _from_job_url(job_url, company=company, locale=locale)
        except ValueError:
            return None

    if not tenant or not site:
        return None
    try:
        host = build_host(tenant, region, host_kind)
    except ValueError:
        return None
    return WorkdayTarget(
        tenant=tenant,
        site=site,
        region=region,
        locale=locale,
        company=company or tenant,
        host=host,
        host_kind=host_kind,
    )


def resolve_job_path(config: dict[str, Any], job_url: str) -> str | None:
    """CXS job path segment (location/slug) from config or URL."""
    configured = config.get("job_path")
    if configured:
        return str(configured).strip("/")
    if not job_url:
        return None
    return extract_job_path(job_url)


def resolve_job_posting_id(
    config: dict[str, Any], job_url: str, job_external_id: str
) -> str | None:
    """Workday job posting anchor id used by the apply API."""
    configured = config.get("job_posting_id")
    if configured:
        return str(configured)
    job_path = resolve_job_path(config, job_url)
    if job_path:
        return job_path.rsplit("/", 1)[-1]
    if job_external_id and "_" in job_external_id:
        return job_external_id
    return job_external_id or None


def _from_job_url(job_url: str, *, company: str, locale: str) -> WorkdayTarget:
    parsed = urlparse(job_url)
    host = parsed.netloc.lower()
    if try_parse_host(host) is None:
        raise ValueError("workday applier job_url must be a Workday careers host")
    board = board_from_url(job_url, locale=locale)
    return WorkdayTarget(
        tenant=board.tenant,
        site=board.site,
        region=board.region,
        locale=board.locale,
        company=company or board.tenant,
        host=board.host,
        host_kind=board.host_kind,
    )
