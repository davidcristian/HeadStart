"""Workday tenant/site resolution for the apply adapter."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

_LOCALE_RE = re.compile(r"^[a-z]{2}-[A-Z]{2}$")
_HOST_WITH_REGION = re.compile(r"^([^.]+)\.(wd\d+)\.myworkdayjobs\.com$", re.IGNORECASE)
_HOST_PLAIN = re.compile(r"^([^.]+)\.myworkdayjobs\.com$", re.IGNORECASE)
_JOB_URL_RE = re.compile(
    r"myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?[^/]+/job/(.+)$",
    re.IGNORECASE,
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

    @property
    def board_url(self) -> str:
        return f"https://{self.host}/{self.locale}/{self.site}"

    def job_page_url(self, job_path: str) -> str:
        return f"{self.board_url}/job/{job_path}"

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

    if job_url:
        try:
            return _from_job_url(job_url, company=company, locale=locale)
        except ValueError:
            return None

    if not tenant or not site:
        return None
    return WorkdayTarget(
        tenant=tenant,
        site=site,
        region=region,
        locale=locale,
        company=company or tenant,
        host=_host(tenant, region),
    )


def resolve_job_path(config: dict[str, Any], job_url: str) -> str | None:
    """CXS job path segment (location/slug) from config or URL."""
    configured = config.get("job_path")
    if configured:
        return str(configured).strip("/")
    if not job_url:
        return None
    match = _JOB_URL_RE.search(job_url)
    if not match:
        return None
    return match.group(1).strip("/")


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
    tenant, region = _parse_host(host)
    parts = [part for part in parsed.path.split("/") if part]

    if parts and _LOCALE_RE.match(parts[0]):
        locale = parts[0]
        parts = parts[1:]
    if not parts:
        raise ValueError("workday applier could not determine site from job_url")
    site = parts[0]
    if not tenant:
        raise ValueError("workday applier could not determine tenant from job_url")
    return WorkdayTarget(
        tenant=tenant,
        site=site,
        region=region,
        locale=locale,
        company=company or tenant,
        host=host,
    )


def _parse_host(host: str) -> tuple[str, str | None]:
    match = _HOST_WITH_REGION.match(host)
    if match:
        return match.group(1), match.group(2)
    match = _HOST_PLAIN.match(host)
    if match:
        return match.group(1), None
    raise ValueError("workday applier job_url must be a *.myworkdayjobs.com URL")


def _host(tenant: str, region: str | None) -> str:
    if region:
        return f"{tenant}.{region}.myworkdayjobs.com"
    return f"{tenant}.myworkdayjobs.com"
