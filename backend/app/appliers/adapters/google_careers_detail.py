"""Google Careers job-detail page parsing helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from app.scrapers.adapters.google_careers_parse import _balanced_json_value

_INIT_DATA_DS0 = "AF_initDataCallback({key: 'ds:0'"
_JOB_RESULTS_RE = re.compile(
    r"/jobs/results/(\d+)-",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class GoogleCareersJobDetail:
    """Apply metadata extracted from a Google Careers job detail page."""

    external_id: str
    title: str
    apply_job_id: str
    apply_url: str
    company: str
    company_resource: str
    location_code: str
    location_label: str


def parse_job_detail_page(html: str) -> GoogleCareersJobDetail | None:
    """Extract apply metadata embedded in a Google Careers job detail page."""
    record = _extract_ds0_record(html)
    if record is None:
        return None
    return _record_to_detail(record)


def resolve_external_id(job_url: str, fallback: str) -> str:
    """Numeric listing id from a /jobs/results/<id>-<slug> URL."""
    match = _JOB_RESULTS_RE.search(job_url)
    return match.group(1) if match else fallback


def parse_apply_link(apply_link: str, *, title: str) -> tuple[str, str, str]:
    """Return (apply_job_id, location_code, apply_url) from a signin/apply link."""
    parsed = urlparse(apply_link)
    params = parse_qs(parsed.query)
    apply_job_id = unquote((params.get("jobId") or [""])[0]).strip()
    if not apply_job_id:
        raise ValueError("google_careers job detail is missing apply jobId token")
    location_code = unquote((params.get("loc") or [""])[0]).strip()
    title_token = unquote((params.get("title") or [title.split(",")[0]])[0]).strip()
    title_token = title_token.replace(" ", "+")
    apply_url = (
        "https://www.google.com/about/careers/applications/apply"
        f"?jobId={apply_job_id}&loc={location_code}&title={title_token}"
    )
    return apply_job_id, location_code, apply_url


def _extract_ds0_record(html: str) -> list[Any] | None:
    idx = html.find(_INIT_DATA_DS0)
    if idx == -1:
        return None
    data_idx = html.find("data:", idx)
    if data_idx == -1:
        return None
    start = html.find("[", data_idx)
    if start == -1:
        return None
    blob = _balanced_json_value(html, start)
    if blob is None:
        return None
    payload = json.loads(blob)
    if not isinstance(payload, list) or not payload:
        return None
    record = payload[0]
    if isinstance(record, list) and record and isinstance(record[0], list):
        record = record[0]
    if not isinstance(record, list):
        return None
    return record


def _record_to_detail(record: list[Any]) -> GoogleCareersJobDetail | None:
    if len(record) < 6:
        return None
    external_id = str(record[0] or "").strip()
    title = str(record[1] or "").strip()
    apply_link = str(record[2] or "").strip()
    company_resource = str(record[5] or "").strip() if len(record) > 5 and record[5] else ""
    company = str(record[7] or "Google").strip() if len(record) > 7 and record[7] else "Google"
    if not external_id or not title or not apply_link:
        return None

    apply_job_id, location_code, apply_url = parse_apply_link(apply_link, title=title)
    location_label = _location_label(record)
    if not company_resource:
        company_resource = ""

    return GoogleCareersJobDetail(
        external_id=external_id,
        title=title,
        apply_job_id=apply_job_id,
        apply_url=apply_url,
        company=company,
        company_resource=company_resource,
        location_code=location_code,
        location_label=location_label,
    )


def _location_label(record: list[Any]) -> str:
    if len(record) <= 9 or not isinstance(record[9], list) or not record[9]:
        return ""
    first = record[9][0]
    if isinstance(first, list) and first and isinstance(first[0], str):
        return first[0]
    return ""
