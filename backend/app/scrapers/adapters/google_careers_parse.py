"""Google Careers HTML parsing helpers for the job-search scraper."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from app.scrapers.types import JobPosting

_INIT_DATA_MARKER = "AF_initDataCallback({key: 'ds:1'"
_JOB_LINK_RE = re.compile(r"jobs/results/(\d+)-([^\"?&]+)")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def parse_search_page(
    html: str,
    *,
    company: str,
    applications_base: str,
    query_params: dict[str, str],
) -> list[JobPosting]:
    """Extract job postings embedded in a Google Careers search results page."""
    records = _extract_job_records(html)
    slug_by_id = dict(_JOB_LINK_RE.findall(html))
    postings: list[JobPosting] = []
    for record in records:
        posting = _to_posting(
            record,
            company=company,
            applications_base=applications_base,
            query_params=query_params,
            slug_by_id=slug_by_id,
        )
        if posting is not None:
            postings.append(posting)
    return postings


def _extract_job_records(html: str) -> list[list[Any]]:
    idx = html.find(_INIT_DATA_MARKER)
    if idx == -1:
        return []
    data_idx = html.find("data:", idx)
    if data_idx == -1:
        return []
    start = html.find("[", data_idx)
    if start == -1:
        return []
    blob = _balanced_json_value(html, start)
    if blob is None:
        return []
    payload = json.loads(blob)
    if not isinstance(payload, list) or not payload:
        return []
    jobs = payload[0]
    if not isinstance(jobs, list):
        return []
    return [job for job in jobs if isinstance(job, list) and job]


def _balanced_json_value(text: str, start: int) -> str | None:
    opener = text[start]
    if opener not in "[{":
        return None
    closer = "]" if opener == "[" else "}"
    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    return None


def _to_posting(
    record: list[Any],
    *,
    company: str,
    applications_base: str,
    query_params: dict[str, str],
    slug_by_id: dict[str, str],
) -> JobPosting | None:
    if len(record) < 2:
        return None
    external_id = str(record[0] or "").strip()
    title = str(record[1] or "").strip()
    if not external_id or not title:
        return None

    posting_company = company
    if len(record) > 7 and isinstance(record[7], str) and record[7].strip():
        posting_company = record[7].strip()

    location = _location_from_record(record)
    posted_at = _posted_at_from_record(record)
    slug = slug_by_id.get(external_id) or _slugify(title)
    url = _job_url(
        applications_base=applications_base,
        external_id=external_id,
        slug=slug,
        query_params=query_params,
    )
    return JobPosting(
        external_id=external_id,
        title=title,
        company=posting_company,
        location=location,
        url=url,
        posted_at=posted_at,
        raw={"record": record},
    )


def _location_from_record(record: list[Any]) -> str:
    if len(record) <= 9 or not isinstance(record[9], list) or not record[9]:
        return ""
    first = record[9][0]
    if isinstance(first, list) and first and isinstance(first[0], str):
        return first[0]
    return ""


def _posted_at_from_record(record: list[Any]) -> datetime | None:
    if len(record) <= 12 or not isinstance(record[12], list) or not record[12]:
        return None
    seconds = record[12][0]
    if not isinstance(seconds, (int, float)):
        return None
    return datetime.fromtimestamp(float(seconds), tz=UTC)


def _slugify(title: str) -> str:
    slug = _SLUG_RE.sub("-", title.lower()).strip("-")
    return slug or "job"


def _job_url(
    *,
    applications_base: str,
    external_id: str,
    slug: str,
    query_params: dict[str, str],
) -> str:
    base = applications_base.rstrip("/")
    path = f"{base}/jobs/results/{external_id}-{slug}"
    if not query_params:
        return path
    return f"{path}?{urlencode(query_params)}"
