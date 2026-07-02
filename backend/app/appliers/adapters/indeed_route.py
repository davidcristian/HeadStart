"""Resolve how an Indeed posting should be applied to."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from app.appliers.adapters.indeed_detail import IndeedJobDetail
from app.appliers.base import has_applier

_GREENHOUSE_JOB_RE = re.compile(
    r"(?:boards|job-boards)\.greenhouse\.io/([^/]+)/jobs/(\d+)",
    re.IGNORECASE,
)
_LEVER_JOB_RE = re.compile(r"jobs(?:\.eu)?\.lever\.co/([^/]+)/([0-9a-f-]{36})", re.IGNORECASE)
_ASHBY_JOB_RE = re.compile(r"jobs\.ashbyhq\.com/([^/]+)/([0-9a-f-]{36})", re.IGNORECASE)
_WORKDAY_JOB_RE = re.compile(
    r"https?://([^.]+)\.(wd\d+)\.myworkdayjobs\.com/.*/job/.*/([^/?#]+)",
    re.IGNORECASE,
)
_WORKDAY_JOB_PLAIN_RE = re.compile(
    r"https?://([^.]+)\.myworkdayjobs\.com/.*/job/.*/([^/?#]+)",
    re.IGNORECASE,
)
_GOOGLE_JOB_RE = re.compile(
    r"/about/careers/applications/jobs/results/(\d+)",
    re.IGNORECASE,
)
_MICROSOFT_JOB_RE = re.compile(
    r"careers\.microsoft\.com/careers/(?:job|apply)/(\d+)",
    re.IGNORECASE,
)
_AMAZON_JOBS_RE = re.compile(
    r"(?:www\.)?amazon\.jobs/(?:(?P<locale>[a-z]{2})/)?jobs/(?P<id>\d+)",
    re.IGNORECASE,
)
_AMAZON_ACCOUNT_RE = re.compile(
    r"account\.amazon\.jobs/jobs/(?P<id>\d+)",
    re.IGNORECASE,
)
_META_CAREERS_RE = re.compile(
    r"(?:www\.)?(?:metacareers|facebookcareers)\.com/(?:jobs|profile/job_details|profile/create_application)/(?P<id>\d+)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ApplyRoute:
    """Resolved apply strategy for one Indeed posting."""

    kind: str  # external_ats | indeed_hosted | unsupported
    adapter_key: str | None
    external_id: str | None
    job_url: str | None
    config: dict[str, Any]
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class AtsJobTarget:
    """Parsed downstream ATS job referenced from an Indeed listing."""

    adapter_key: str
    external_id: str
    job_url: str
    config: dict[str, Any]


def resolve_apply_route(detail: IndeedJobDetail) -> ApplyRoute:
    """Pick external ATS delegation, Indeed-hosted Easy Apply, or unsupported."""
    if detail.expired:
        return ApplyRoute(
            kind="unsupported",
            adapter_key=None,
            external_id=None,
            job_url=None,
            config={},
            reason="indeed posting is expired or no longer available",
        )

    if detail.external_apply_url:
        target = parse_ats_job_url(detail.external_apply_url)
        if target is not None and has_applier(target.adapter_key):
            return ApplyRoute(
                kind="external_ats",
                adapter_key=target.adapter_key,
                external_id=target.external_id,
                job_url=target.job_url,
                config=target.config,
            )
        if target is not None:
            return ApplyRoute(
                kind="unsupported",
                adapter_key=target.adapter_key,
                external_id=target.external_id,
                job_url=target.job_url,
                config=target.config,
                reason=(
                    f"indeed listing redirects to {target.adapter_key}, "
                    "which has no apply adapter"
                ),
            )
        return ApplyRoute(
            kind="unsupported",
            adapter_key=None,
            external_id=None,
            job_url=detail.external_apply_url,
            config={},
            reason=(
                "indeed listing uses an external apply URL that is not a supported ATS "
                f"({detail.external_apply_url})"
            ),
        )

    if detail.easily_apply:
        return ApplyRoute(
            kind="indeed_hosted",
            adapter_key="indeed",
            external_id=detail.job_key,
            job_url=None,
            config={},
        )

    return ApplyRoute(
        kind="unsupported",
        adapter_key=None,
        external_id=None,
        job_url=None,
        config={},
        reason="indeed posting has no Easy Apply button and no external ATS apply URL",
    )


def parse_ats_job_url(url: str) -> AtsJobTarget | None:
    """Map an employer apply URL embedded in an Indeed listing to a known ATS target."""
    normalized = url.strip()
    if not normalized:
        return None

    greenhouse = _GREENHOUSE_JOB_RE.search(normalized)
    if greenhouse:
        token, job_id = greenhouse.group(1), greenhouse.group(2)
        return AtsJobTarget(
            adapter_key="greenhouse",
            external_id=job_id,
            job_url=normalized,
            config={"board_token": token},
        )

    lever = _LEVER_JOB_RE.search(normalized)
    if lever:
        site, posting_id = lever.group(1), lever.group(2)
        config: dict[str, Any] = {"site": site}
        if ".eu." in normalized.lower():
            config["region"] = "eu"
        return AtsJobTarget(
            adapter_key="lever",
            external_id=posting_id,
            job_url=normalized,
            config=config,
        )

    ashby = _ASHBY_JOB_RE.search(normalized)
    if ashby:
        board, posting_id = ashby.group(1), ashby.group(2)
        return AtsJobTarget(
            adapter_key="ashby",
            external_id=posting_id,
            job_url=normalized,
            config={"board": board},
        )

    workday = _WORKDAY_JOB_RE.search(normalized) or _WORKDAY_JOB_PLAIN_RE.search(normalized)
    if workday:
        tenant = workday.group(1)
        if len(workday.groups()) == 3:
            region = workday.group(2)
            job_segment = workday.group(3)
            config = {"tenant": tenant, "region": region}
        else:
            job_segment = workday.group(2)
            config = {"tenant": tenant}
        site = _workday_site_from_url(normalized)
        if site:
            config["site"] = site
        external_id = _workday_external_id(job_segment)
        return AtsJobTarget(
            adapter_key="workday",
            external_id=external_id,
            job_url=normalized,
            config=config,
        )

    google = _GOOGLE_JOB_RE.search(normalized)
    if google:
        return AtsJobTarget(
            adapter_key="google_careers",
            external_id=google.group(1),
            job_url=normalized,
            config={"company": "Google", "portal_id": "google"},
        )

    microsoft = _MICROSOFT_JOB_RE.search(normalized)
    if microsoft:
        position_id = microsoft.group(1)
        return AtsJobTarget(
            adapter_key="microsoft_careers",
            external_id=position_id,
            job_url=normalized,
            config={
                "company": "Microsoft",
                "portal_id": "microsoft",
                "domain": "microsoft.com",
            },
        )

    amazon = _AMAZON_JOBS_RE.search(normalized) or _AMAZON_ACCOUNT_RE.search(normalized)
    if amazon:
        job_id = amazon.group("id")
        amazon_config: dict[str, Any] = {"company": "Amazon", "portal_id": "amazon"}
        locale = amazon.groupdict().get("locale")
        if locale:
            amazon_config["locale"] = locale.lower()
        return AtsJobTarget(
            adapter_key="amazon_jobs",
            external_id=job_id,
            job_url=normalized,
            config=amazon_config,
        )

    meta = _META_CAREERS_RE.search(normalized)
    if meta:
        job_id = meta.group("id")
        return AtsJobTarget(
            adapter_key="meta_careers",
            external_id=job_id,
            job_url=normalized,
            config={"company": "Meta", "portal_id": "meta"},
        )

    return None


def _workday_site_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and _LOCALE_RE.match(parts[0]):
        return parts[1]
    return parts[0] if parts else None


def _workday_external_id(job_segment: str) -> str:
    if "_" in job_segment:
        return job_segment.rsplit("_", 1)[-1]
    return job_segment


_LOCALE_RE = re.compile(r"^[a-z]{2}-[A-Z]{2}$")
