"""Parse Meta Careers GraphQL search responses and page tokens."""

from __future__ import annotations

import json
import re
from typing import Any

from app.scrapers.types import JobPosting

_ORIGIN = "https://www.metacareers.com"
_LSD_TOKEN_RE = re.compile(r'"LSD",\[\],\{"token":"([^"]+)"\}')
_LSD_INPUT_RE = re.compile(r'name="lsd"\s+value="([^"]+)"', re.IGNORECASE)


def extract_lsd_token(html: str) -> str:
    """Return the anti-CSRF ``lsd`` token embedded in a Meta careers page."""
    for pattern in (_LSD_TOKEN_RE, _LSD_INPUT_RE):
        match = pattern.search(html)
        if match:
            token = match.group(1).strip()
            if token:
                return token
    raise ValueError("meta_careers page is missing an lsd token")


def parse_search_response(data: Any, *, company: str) -> list[JobPosting]:
    """Convert a CareersJobSearchResultsDataQuery payload into job postings."""
    if not isinstance(data, dict):
        raise ValueError("meta_careers GraphQL returned unexpected payload (expected object)")

    root = data.get("data")
    if not isinstance(root, dict):
        message = _first_graphql_error(data)
        raise ValueError(message or "meta_careers GraphQL returned no data")

    search = root.get("job_search_with_featured_jobs")
    if not isinstance(search, dict):
        raise ValueError("meta_careers GraphQL returned unexpected job search payload")

    jobs = search.get("all_jobs")
    if not isinstance(jobs, list):
        raise ValueError("meta_careers GraphQL returned unexpected all_jobs field (expected array)")

    postings: list[JobPosting] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        postings.append(_to_posting(job, company=company))
    return postings


def parse_graphql_json(body: str, *, company: str) -> list[JobPosting]:
    """Parse a GraphQL JSON response body into job postings."""
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError("meta_careers GraphQL returned invalid JSON") from exc
    return parse_search_response(data, company=company)


def _first_graphql_error(data: dict[str, Any]) -> str | None:
    errors = data.get("errors")
    if not isinstance(errors, list) or not errors:
        return None
    first = errors[0]
    if isinstance(first, dict):
        message = first.get("message")
        if isinstance(message, str) and message.strip():
            return f"meta_careers GraphQL error: {message.strip()}"
    return "meta_careers GraphQL returned errors"


def _to_posting(job: dict[str, Any], *, company: str) -> JobPosting:
    external_id = str(job.get("id") or "").strip()
    if not external_id:
        raise ValueError("meta_careers job is missing id")
    title = str(job.get("title") or "").strip()
    location = _format_locations(job.get("locations"))
    return JobPosting(
        external_id=external_id,
        title=title,
        company=company,
        location=location,
        url=f"{_ORIGIN}/jobs/{external_id}/",
        raw=job,
    )


def _format_locations(raw: Any) -> str:
    if not isinstance(raw, list):
        return ""
    locations = [str(item).strip() for item in raw if str(item).strip()]
    return "; ".join(locations)
