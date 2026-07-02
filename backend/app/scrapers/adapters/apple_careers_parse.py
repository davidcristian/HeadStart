"""Parse Apple Careers search pages embedded hydration JSON."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from app.scrapers.types import JobPosting

_ORIGIN = "https://jobs.apple.com"
_HYDRATION_RE = re.compile(
    r'window\.__staticRouterHydrationData\s*=\s*JSON\.parse\("(?P<payload>.+?)"\);',
    re.DOTALL,
)


def extract_hydration_data(html: str) -> dict[str, Any]:
    """Return the parsed static-router hydration object from a search page."""
    match = _HYDRATION_RE.search(html)
    if match is None:
        raise ValueError("apple_careers page is missing static router hydration data")
    raw = bytes(match.group("payload"), "utf-8").decode("unicode_escape")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("apple_careers hydration payload is not valid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("apple_careers hydration payload must be an object")
    return data


def parse_search_html(
    html: str,
    *,
    company: str,
    locale: str,
) -> tuple[list[JobPosting], int]:
    """Parse one Apple Careers search page into postings and total record count."""
    data = extract_hydration_data(html)
    loader = data.get("loaderData")
    if not isinstance(loader, dict):
        raise ValueError("apple_careers hydration payload is missing loaderData")
    search = loader.get("search")
    if not isinstance(search, dict):
        raise ValueError("apple_careers hydration payload is missing search loader data")
    results = search.get("searchResults")
    if not isinstance(results, list):
        raise ValueError("apple_careers searchResults must be an array")
    raw_total = search.get("totalRecords", len(results))
    total = int(raw_total) if isinstance(raw_total, (int, float)) else len(results)
    postings = [
        _to_posting(job, company=company, locale=locale) for job in results if isinstance(job, dict)
    ]
    return postings, total


def _to_posting(job: dict[str, Any], *, company: str, locale: str) -> JobPosting:
    external_id = str(job.get("reqId") or job.get("id") or job.get("positionId") or "").strip()
    if not external_id:
        raise ValueError("apple_careers job is missing id")
    title = str(job.get("postingTitle") or "").strip()
    location = _format_location(job)
    url = _job_url(job, locale=locale)
    posted_at = _posted_at(job)
    return JobPosting(
        external_id=external_id,
        title=title,
        company=company,
        location=location,
        url=url,
        posted_at=posted_at,
        raw=job,
    )


def _format_location(job: dict[str, Any]) -> str:
    locations = job.get("locations")
    if not isinstance(locations, list) or not locations:
        return ""
    parts: list[str] = []
    for item in locations:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        city = str(item.get("city") or "").strip()
        state = str(item.get("stateProvince") or "").strip()
        country = str(item.get("countryName") or "").strip()
        if city and state:
            parts.append(f"{city}, {state}")
        elif city:
            parts.append(city)
        elif name:
            parts.append(name)
        elif country:
            parts.append(country)
    return "; ".join(dict.fromkeys(parts))


def _job_url(job: dict[str, Any], *, locale: str) -> str:
    req_id = str(job.get("reqId") or job.get("id") or job.get("positionId") or "").strip()
    slug = str(job.get("transformedPostingTitle") or "").strip()
    team = job.get("team")
    team_code = ""
    if isinstance(team, dict):
        team_code = str(team.get("teamCode") or "").strip()
    if req_id and slug:
        path = f"/{locale}/details/{req_id}/{slug}"
        if team_code:
            path = f"{path}?team={team_code}"
        return f"{_ORIGIN}{path}"
    return f"{_ORIGIN}/{locale}/search"


def _posted_at(job: dict[str, Any]) -> datetime | None:
    raw = str(job.get("postDateInGMT") or "").strip()
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
