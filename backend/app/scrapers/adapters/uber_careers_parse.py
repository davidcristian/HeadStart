"""Parse Uber Careers ``loadSearchJobsResults`` API payloads."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.scrapers.types import JobPosting


def parse_search_response(
    payload: dict[str, Any],
    *,
    company: str,
    careers_base_url: str,
) -> tuple[list[JobPosting], int | None]:
    """Parse one search page into postings and the declared total count."""
    data = payload.get("data")
    if not isinstance(data, dict):
        return [], None
    total = coerce_int64(data.get("totalResults"))
    results = data.get("results")
    if not isinstance(results, list):
        return [], total
    postings = [
        posting
        for item in results
        if isinstance(item, dict)
        for posting in [_to_posting(item, company=company, careers_base_url=careers_base_url)]
    ]
    return postings, total


def coerce_int64(value: Any) -> int | None:
    """Decode Uber's protobuf-style int64 objects and plain integers."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, dict):
        low = value.get("low")
        high = value.get("high")
        if low is None and high is None:
            return None
        return (int(high or 0) << 32) + int(low or 0)
    return None


def format_location(node: Any) -> str:
    """Flatten Uber's ``location`` / ``allLocations`` nodes into one string."""
    if node is None:
        return ""
    if isinstance(node, str):
        return " ".join(node.split())
    if isinstance(node, list):
        parts = [format_location(item) for item in node]
        seen: list[str] = []
        for part in parts:
            if part and part not in seen:
                seen.append(part)
        return "; ".join(seen)
    if isinstance(node, dict):
        city = str(node.get("city") or "").strip()
        region = str(node.get("region") or "").strip()
        country_name = str(node.get("countryName") or "").strip()
        country = str(node.get("country") or "").strip()
        components = [part for part in (city, region, country_name or country) if part]
        if components:
            return ", ".join(components)
    return ""


def _to_posting(item: dict[str, Any], *, company: str, careers_base_url: str) -> JobPosting:
    external_id = str(item.get("id") or "").strip()
    if not external_id:
        raise ValueError("uber_careers job is missing id")
    title = str(item.get("title") or "").strip()
    location = format_location(item.get("location"))
    if not location:
        location = format_location(item.get("allLocations"))
    url = f"{careers_base_url.rstrip('/')}/{external_id}"
    return JobPosting(
        external_id=external_id,
        title=title,
        company=company,
        location=location,
        url=url,
        posted_at=_posted_at(item),
        raw=item,
    )


def _posted_at(item: dict[str, Any]) -> datetime | None:
    for key in ("creationDate", "updatedDate"):
        raw = str(item.get(key) or "").strip()
        if not raw:
            continue
        normalized = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return None
