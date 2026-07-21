"""Shared Workday host/path helpers for ``*.myworkdayjobs.com`` and ``*.myworkdaysite.com``.

Classic careers boards live on ``{tenant}.{region}.myworkdayjobs.com/{locale}/{site}``.
Some employers (e.g. Snap) publish on ``{region}.myworkdaysite.com/recruiting/{tenant}/{site}``
instead. Both expose the same public CXS jobs API under ``/wday/cxs/{tenant}/{site}/jobs``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

HOST_KIND_JOBS = "jobs"
HOST_KIND_SITE = "site"

_LOCALE_RE = re.compile(r"^[a-z]{2}-[A-Z]{2}$")
_HOST_WITH_REGION = re.compile(r"^([^.]+)\.(wd\d+)\.myworkdayjobs\.com$", re.IGNORECASE)
_HOST_PLAIN = re.compile(r"^([^.]+)\.myworkdayjobs\.com$", re.IGNORECASE)
_HOST_SITE = re.compile(r"^(wd\d+)\.myworkdaysite\.com$", re.IGNORECASE)


@dataclass(frozen=True)
class WorkdayBoard:
    """Resolved Workday tenant/site coordinates for scrape or apply."""

    tenant: str
    site: str
    region: str | None
    locale: str
    host: str
    host_kind: str = HOST_KIND_JOBS

    @property
    def api_url(self) -> str:
        return f"https://{self.host}/wday/cxs/{self.tenant}/{self.site}/jobs"

    @property
    def api_base(self) -> str:
        return f"https://{self.host}/wday/cxs/{self.tenant}"

    @property
    def board_url(self) -> str:
        if self.host_kind == HOST_KIND_SITE:
            return f"https://{self.host}/recruiting/{self.tenant}/{self.site}"
        return f"https://{self.host}/{self.locale}/{self.site}"

    def job_url(self, external_path: str) -> str:
        if not external_path:
            return self.board_url
        if self.host_kind == HOST_KIND_SITE:
            path = external_path if external_path.startswith("/") else f"/{external_path}"
            return f"https://{self.host}/recruiting/{self.tenant}/{self.site}{path}"
        if external_path.startswith("/"):
            return f"https://{self.host}/{self.locale}/{self.site}{external_path}"
        return f"https://{self.host}/{self.locale}/{self.site}/{external_path}"


def normalize_host_kind(value: object | None) -> str:
    """Map config ``host_kind`` to ``jobs`` or ``site`` (default ``jobs``)."""
    raw = str(value or HOST_KIND_JOBS).strip().lower()
    if raw in {HOST_KIND_SITE, "myworkdaysite", "site.com"}:
        return HOST_KIND_SITE
    return HOST_KIND_JOBS


def build_host(tenant: str, region: str | None, host_kind: str = HOST_KIND_JOBS) -> str:
    """Construct the careers host for the given tenant/region/kind."""
    kind = normalize_host_kind(host_kind)
    if kind == HOST_KIND_SITE:
        if not region:
            raise ValueError("workday myworkdaysite.com hosts require config.region (e.g. wd1)")
        return f"{region}.myworkdaysite.com"
    if region:
        return f"{tenant}.{region}.myworkdayjobs.com"
    return f"{tenant}.myworkdayjobs.com"


def parse_host(host: str) -> tuple[str, str | None, str]:
    """Return ``(tenant_or_empty, region, host_kind)`` for a Workday careers host.

    Site hosts encode the region in the hostname and leave tenant empty. Callers
    must read tenant from the ``/recruiting/{tenant}/{site}`` path or CXS path.
    """
    match = _HOST_WITH_REGION.match(host)
    if match:
        return match.group(1), match.group(2), HOST_KIND_JOBS
    match = _HOST_PLAIN.match(host)
    if match:
        return match.group(1), None, HOST_KIND_JOBS
    match = _HOST_SITE.match(host)
    if match:
        return "", match.group(1), HOST_KIND_SITE
    raise ValueError(
        "workday URL must be a *.myworkdayjobs.com or *.myworkdaysite.com careers host"
    )


def try_parse_host(host: str) -> tuple[str, str | None, str] | None:
    """Like ``parse_host`` but returns ``None`` instead of raising."""
    try:
        return parse_host(host)
    except ValueError:
        return None


def board_from_url(url: str, *, locale: str = "en-US") -> WorkdayBoard:
    """Resolve tenant/site/host from a careers board, job, or CXS URL."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    tenant, region, host_kind = parse_host(host)
    parts = parsed.path.strip("/").split("/") if parsed.path.strip("/") else []

    if len(parts) >= 2 and parts[0] == "wday" and parts[1] == "cxs":
        if len(parts) < 4 or not (parts[2] and parts[3]):
            raise ValueError("workday CXS URL is missing tenant or site")
        tenant = parts[2] or tenant
        site = parts[3]
        return WorkdayBoard(
            tenant=tenant,
            site=site,
            region=region,
            locale=locale,
            host=host,
            host_kind=host_kind,
        )

    if host_kind == HOST_KIND_SITE:
        if len(parts) >= 3 and parts[0].lower() == "recruiting":
            tenant = parts[1] or tenant
            site = parts[2]
            if not tenant or not site:
                raise ValueError("workday myworkdaysite URL is missing tenant or site")
            return WorkdayBoard(
                tenant=tenant,
                site=site,
                region=region,
                locale=locale,
                host=host,
                host_kind=HOST_KIND_SITE,
            )
        raise ValueError("workday myworkdaysite URL must include /recruiting/{tenant}/{site}")

    if parts and _LOCALE_RE.match(parts[0]):
        locale = parts[0]
        parts = parts[1:]
    if not parts:
        raise ValueError("workday scraper could not determine site from query_url")
    site = parts[0]
    if not tenant:
        raise ValueError("workday scraper could not determine tenant from query_url")
    return WorkdayBoard(
        tenant=tenant,
        site=site,
        region=region,
        locale=locale,
        host=host,
        host_kind=HOST_KIND_JOBS,
    )


def extract_job_path(url: str) -> str | None:
    """CXS job path (location/slug) from a careers job URL on either host kind."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    parsed_host = try_parse_host(host)
    if parsed_host is None:
        return None
    _, _, host_kind = parsed_host
    parts = [part for part in parsed.path.split("/") if part]
    if host_kind == HOST_KIND_SITE:
        # /recruiting/{tenant}/{site}/job/{rest}
        if len(parts) >= 5 and parts[0].lower() == "recruiting" and parts[3].lower() == "job":
            return "/".join(parts[4:]).strip("/") or None
        return None
    # /{locale?}/{site}/job/{rest}
    if parts and _LOCALE_RE.match(parts[0]):
        parts = parts[1:]
    if len(parts) >= 3 and parts[1].lower() == "job":
        return "/".join(parts[2:]).strip("/") or None
    return None
