"""Fetch and parse Meta Careers job detail metadata for apply previews."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.appliers.adapters.meta_careers_common import (
    JOB_DETAILS_DOC_ID,
    JOB_DETAILS_QUERY,
    job_details_url,
)
from app.appliers.adapters.meta_careers_graphql import fetch_lsd_token, post_graphql
from app.scrapers.http import HttpClient


@dataclass(frozen=True, slots=True)
class MetaCareersJobDetail:
    """Job metadata returned by CandidatePortalJobDetailsViewQuery."""

    requisition_id: str
    title: str
    locations: tuple[str, ...]
    departments: tuple[str, ...]
    description_html: str
    minimum_qualifications: tuple[str, ...]
    preferred_qualifications: tuple[str, ...]
    responsibilities: tuple[str, ...]


def fetch_job_detail(http: HttpClient, requisition_id: str) -> MetaCareersJobDetail:
    """Load public job detail metadata for one requisition."""
    page_url = job_details_url(requisition_id)
    lsd = fetch_lsd_token(http, page_url)
    response = post_graphql(
        http,
        lsd=lsd,
        friendly_name=JOB_DETAILS_QUERY,
        doc_id=JOB_DETAILS_DOC_ID,
        variables={
            "requisitionID": requisition_id,
            "renderLoggedInView": False,
        },
    )
    return parse_job_detail_response(response, requisition_id=requisition_id)


def parse_job_detail_response(data: dict[str, Any], *, requisition_id: str) -> MetaCareersJobDetail:
    """Convert a CandidatePortalJobDetailsViewQuery payload into a detail record."""
    root = data.get("data")
    if not isinstance(root, dict):
        raise ValueError("meta_careers job detail response is missing data")
    job = root.get("xcp_requisition_job_description")
    if not isinstance(job, dict):
        raise ValueError(
            "meta_careers job detail response is missing xcp_requisition_job_description"
        )

    title = str(job.get("title") or "").strip()
    if not title:
        raise ValueError("meta_careers job detail is missing title")

    return MetaCareersJobDetail(
        requisition_id=str(job.get("id") or requisition_id).strip(),
        title=title,
        locations=_string_list(job.get("locations")),
        departments=_string_list(job.get("departments")),
        description_html=_html_blob(job.get("description")),
        minimum_qualifications=_item_list(job.get("minimum_qualifications")),
        preferred_qualifications=_item_list(job.get("preferred_qualifications")),
        responsibilities=_item_list(job.get("responsibilities")),
    )


def _string_list(raw: Any) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    return tuple(str(item).strip() for item in raw if str(item).strip())


def _item_list(raw: Any) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    items: list[str] = []
    for entry in raw:
        if isinstance(entry, dict):
            text = str(entry.get("item") or "").strip()
            if text:
                items.append(text)
    return tuple(items)


def _html_blob(raw: Any) -> str:
    if not isinstance(raw, str):
        return ""
    text = raw.strip()
    if not text:
        return ""
    if text.startswith("{"):
        try:
            import json

            payload = json.loads(text)
        except json.JSONDecodeError:
            return text
        if isinstance(payload, dict):
            html = payload.get("__html")
            if isinstance(html, str):
                return html
    return text
