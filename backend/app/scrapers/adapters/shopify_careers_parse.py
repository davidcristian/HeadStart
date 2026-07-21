"""Parse Shopify Careers pages embedded React Router flight stream."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from app.scrapers.types import JobPosting

_ORIGIN = "https://www.shopify.com"
_STREAM_RE = re.compile(
    r"window\.__reactRouterContext\.streamController\.enqueue\("
    r'"(?P<payload>(?:\\.|[^"\\])*)"\)',
)
_CAREERS_ROUTE = "($locale)/careers"
# Cap flight-graph recursion so a long non-cyclic reference chain cannot
# exhaust Python's recursion limit. Real careers payloads nest shallowly.
_MAX_RESOLVE_DEPTH = 64


def parse_careers_html(html: str, *, company: str) -> list[JobPosting]:
    """Parse a Shopify Careers page into normalized job postings."""
    records = extract_job_records(html)
    postings: list[JobPosting] = []
    for record in records:
        posting = record.get("jobPosting")
        if not isinstance(posting, dict):
            continue
        if posting.get("isListed") is False:
            continue
        postings.append(_to_posting(posting, company=company))
    return postings


def extract_job_records(html: str) -> list[dict[str, Any]]:
    """Return raw ``jobPostingsWithJobs`` entries from the careers page."""
    stream = _decode_stream(html)
    for index, value in enumerate(stream):
        if value == _CAREERS_ROUTE and index + 1 < len(stream):
            careers = _resolve_node(index + 1, stream)
            if isinstance(careers, dict):
                jobs = careers.get("jobPostingsWithJobs")
                if isinstance(jobs, list):
                    return [job for job in jobs if isinstance(job, dict)]
    raise ValueError("shopify_careers page is missing careers loader data")


def _decode_stream(html: str) -> list[Any]:
    match = _STREAM_RE.search(html)
    if match is None:
        raise ValueError("shopify_careers page is missing react router stream data")
    raw = bytes(match.group("payload"), "utf-8").decode("unicode_escape")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("shopify_careers stream payload is not valid JSON") from exc
    if not isinstance(data, list):
        raise ValueError("shopify_careers stream payload must be an array")
    return data


def _resolve_node(
    index: int,
    stream: list[Any],
    stack: set[int] | None = None,
    *,
    depth: int = 0,
) -> Any:
    """Resolve a React Router flight reference graph."""
    if stack is None:
        stack = set()
    if index < 0 or depth > _MAX_RESOLVE_DEPTH:
        return None
    if index in stack:
        return None
    stack = set(stack)
    stack.add(index)
    value = stream[index]
    child_depth = depth + 1
    if isinstance(value, list):
        return [
            (
                _resolve_node(item, stream, stack, depth=child_depth)
                if isinstance(item, int)
                else item
            )
            for item in value
        ]
    if isinstance(value, dict):
        if value and all(str(key).startswith("_") for key in value):
            resolved: dict[str, Any] = {}
            for ref_key, ref_index in value.items():
                try:
                    key_index = int(ref_key[1:])
                except ValueError:
                    key = ref_key
                else:
                    key = stream[key_index] if 0 <= key_index < len(stream) else ref_key
                resolved[str(key)] = (
                    _resolve_node(ref_index, stream, stack, depth=child_depth)
                    if isinstance(ref_index, int)
                    else ref_index
                )
            return resolved
        return {
            key: (
                _resolve_node(item, stream, stack, depth=child_depth)
                if isinstance(item, int)
                else item
            )
            for key, item in value.items()
        }
    return value


def _to_posting(job: dict[str, Any], *, company: str) -> JobPosting:
    external_id = str(job.get("id") or "").strip()
    if not external_id:
        raise ValueError("shopify_careers job is missing id")
    title = str(job.get("title") or "").strip()
    location = _format_location(job)
    url = str(job.get("externalLink") or _detail_url(job)).strip()
    return JobPosting(
        external_id=external_id,
        title=title,
        company=company,
        location=location,
        url=url,
        posted_at=_posted_at(job),
        raw=job,
    )


def _format_location(job: dict[str, Any]) -> str:
    workplace = str(job.get("workplaceType") or "").strip()
    location = str(job.get("locationName") or job.get("locationExternalName") or "").strip()
    if workplace.lower() == "remote" and location:
        return f"Remote - {location}"
    if location:
        return location
    return workplace


def _detail_url(job: dict[str, Any]) -> str:
    external_id = str(job.get("id") or "").strip()
    if external_id:
        return f"{_ORIGIN}/careers?ashby_jid={external_id}"
    return f"{_ORIGIN}/careers"


def _posted_at(job: dict[str, Any]) -> datetime | None:
    for key in ("updatedAt", "publishedDate"):
        raw = str(job.get(key) or "").strip()
        if not raw:
            continue
        normalized = raw.replace("Z", "+00:00")
        if "T" not in normalized:
            normalized = f"{normalized}T00:00:00+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return None
