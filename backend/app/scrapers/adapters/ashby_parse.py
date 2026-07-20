"""Shared Ashby Postings API parsing helpers."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse, urlunparse

from app.scrapers.dates import parse_iso8601
from app.scrapers.types import JobPosting

ASHBY_API = "https://api.ashbyhq.com/posting-api/job-board/{board}"


def encode_board_slug(board: str) -> str:
    """Percent-encode an Ashby board slug (spaces/names like ``Superhuman Platform Inc``)."""
    return quote(unquote(board.strip()), safe="")


def api_url(board: str, include_compensation: bool) -> str:
    """Build the public Ashby Postings API URL for a board slug."""
    url = ASHBY_API.format(board=encode_board_slug(board))
    if include_compensation:
        return f"{url}?includeCompensation=true"
    return url


def with_compensation(url: str, include_compensation: bool) -> str:
    """Append includeCompensation when the caller asked for salary data."""
    if not include_compensation:
        return url
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    if "includeCompensation" not in params:
        params["includeCompensation"] = ["true"]
    query = urlencode({k: v[0] for k, v in params.items()})
    return urlunparse(parsed._replace(query=query))


def parse_ashby_board_payload(data: dict[str, Any], company: str) -> list[JobPosting]:
    """Normalize an Ashby Postings API response into job postings."""
    jobs = data.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("ashby API returned unexpected jobs field (expected a JSON array)")
    listed = [job for job in jobs if isinstance(job, dict) and job.get("isListed", True)]
    return [to_posting(job, company) for job in listed]


def to_posting(job: dict[str, Any], company: str) -> JobPosting:
    """Map one Ashby job object to a normalized posting."""
    location = str(job.get("location") or "")
    if not location and isinstance(job.get("secondaryLocations"), list):
        secondary = job["secondaryLocations"]
        if secondary and isinstance(secondary[0], dict):
            location = str(secondary[0].get("location") or "")
    posted_at = parse_iso8601(job.get("publishedAt"))
    return JobPosting(
        external_id=str(job.get("id", "")),
        title=str(job.get("title", "")),
        company=company,
        location=location,
        url=str(job.get("jobUrl", "")),
        posted_at=posted_at,
        raw=job,
    )
