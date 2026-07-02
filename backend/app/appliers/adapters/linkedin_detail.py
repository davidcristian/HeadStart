"""LinkedIn guest job-posting page parsing helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from selectolax.parser import HTMLParser

from app.appliers.adapters.linkedin_common import extract_code_comment

_AUTH_MARKERS = (
    "authwall",
    "Sign in to LinkedIn",
    "Join LinkedIn",
    "checkpoint/challenge",
)
_APPLY_ONSITE = "public_jobs_apply-link-onsite"
_APPLY_OFFSITE = "public_jobs_apply-link-offsite"


@dataclass(frozen=True, slots=True)
class LinkedInJobDetail:
    """Apply metadata extracted from a LinkedIn job posting page."""

    job_id: str
    title: str
    company: str
    reference_id: str | None
    tracking_id: str | None
    easy_apply: bool
    offsite_apply: bool
    external_apply_url: str | None
    expired: bool


def parse_job_posting_page(html: str, *, fallback_job_id: str = "") -> LinkedInJobDetail | None:
    """Extract apply metadata from LinkedIn guest job-posting HTML."""
    reject_auth_wall(html)
    tree = HTMLParser(html)
    job_id = extract_code_comment(html, "decoratedJobPostingId") or fallback_job_id.strip() or ""
    title_node = tree.css_first("h2.top-card-layout__title, h2.topcard__title")
    title = title_node.text(strip=True) if title_node else ""
    company_node = tree.css_first("a.topcard__org-name-link")
    company = company_node.text(strip=True) if company_node else ""
    apply_button = tree.css_first(
        f'button[data-tracking-control-name="{_APPLY_ONSITE}"],'
        f'button[data-tracking-control-name="{_APPLY_OFFSITE}"]'
    )
    easy_apply = False
    offsite_apply = False
    tracking_id = None
    if apply_button is not None:
        attrs = apply_button.attributes or {}
        control = str(attrs.get("data-tracking-control-name") or "")
        easy_apply = control == _APPLY_ONSITE
        offsite_apply = control == _APPLY_OFFSITE
        tracking_id = str(attrs.get("data-tracking-id") or "").strip() or None
    reference_id = extract_code_comment(html, "referenceId")
    if not job_id or not title:
        return None
    expired = "no longer accepting applications" in html.lower()
    return LinkedInJobDetail(
        job_id=job_id,
        title=title,
        company=company,
        reference_id=reference_id,
        tracking_id=tracking_id,
        easy_apply=easy_apply,
        offsite_apply=offsite_apply,
        external_apply_url=None,
        expired=expired,
    )


def merge_external_apply_url(
    detail: LinkedInJobDetail,
    external_apply_url: str | None,
) -> LinkedInJobDetail:
    """Return a copy of detail with an external apply URL attached."""
    if not external_apply_url:
        return detail
    return LinkedInJobDetail(
        job_id=detail.job_id,
        title=detail.title,
        company=detail.company,
        reference_id=detail.reference_id,
        tracking_id=detail.tracking_id,
        easy_apply=detail.easy_apply,
        offsite_apply=detail.offsite_apply,
        external_apply_url=external_apply_url,
        expired=detail.expired,
    )


def reject_auth_wall(html: str) -> None:
    """Raise when LinkedIn serves an auth wall instead of the job page."""
    lowered = html.lower()
    if any(marker.lower() in lowered for marker in _AUTH_MARKERS):
        raise ValueError(
            "linkedin returned an auth wall; add session cookies via Site credentials "
            "or retry later"
        )


def extract_company_apply_url(payload: dict[str, Any]) -> str | None:
    """Read companyApplyUrl from Voyager GraphQL or REST job posting payloads."""
    for node in _payload_nodes(payload):
        url = node.get("companyApplyUrl")
        if isinstance(url, str) and url.strip():
            return url.strip()
        apply_method = node.get("applyMethod")
        if isinstance(apply_method, dict):
            for key, value in apply_method.items():
                if "OffsiteApply" in key and isinstance(value, dict):
                    offsite_url = value.get("companyApplyUrl")
                    if isinstance(offsite_url, str) and offsite_url.strip():
                        return offsite_url.strip()
    return None


def _payload_nodes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = [payload]
    data = payload.get("data")
    if isinstance(data, dict):
        nodes.append(data)
        nested = data.get("jobsDashJobPostingsById")
        if isinstance(nested, dict):
            nodes.append(nested)
    nested = payload.get("jobsDashJobPostingsById")
    if isinstance(nested, dict):
        nodes.append(nested)
    return nodes
