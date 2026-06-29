"""Post-scrape posting filters applied from a search's `filters` JSON.

Filters run in the pipeline after scraping and before deduplication. Empty or
unknown filter keys are ignored so adapters can keep passing filters through
`ScrapeContext` without the pipeline applying them twice.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from app.scrapers.types import JobPosting
from app.services.compensation import meets_min_salary

Workplace = Literal["remote", "hybrid", "onsite"]

_WORKPLACE_ALIASES: dict[str, Workplace] = {
    "remote": "remote",
    "hybrid": "hybrid",
    "onsite": "onsite",
    "on-site": "onsite",
    "on site": "onsite",
}


def apply_posting_filters(
    postings: list[JobPosting], filters: dict[str, Any]
) -> tuple[list[JobPosting], int]:
    """Return postings that match `filters` and how many were removed."""
    if not filters or not postings:
        return postings, 0

    kept: list[JobPosting] = []
    removed = 0
    for posting in postings:
        if matches_posting_filters(posting, filters):
            kept.append(posting)
        else:
            removed += 1
    return kept, removed


def matches_posting_filters(posting: JobPosting, filters: dict[str, Any]) -> bool:
    """True when a posting satisfies all configured filter fields."""
    haystack = _search_text(posting)

    include = _terms(filters.get("keywords_include")) or _terms(filters.get("keywords"))
    if include and not all(term in haystack for term in include):
        return False

    exclude = _terms(filters.get("keywords_exclude"))
    if exclude and any(term in haystack for term in exclude):
        return False

    locations = _terms(filters.get("location"))
    if locations:
        location_text = posting.location.lower()
        if not any(term in location_text for term in locations):
            return False

    workplaces = _workplace_terms(filters.get("workplace"))
    if workplaces:
        inferred = infer_workplace(posting)
        if inferred is not None and inferred not in workplaces:
            return False

    min_salary = _min_salary(filters.get("min_salary"))
    if min_salary is not None:
        currency = _salary_currency(filters.get("salary_currency"))
        if not meets_min_salary(posting, min_salary, currency):
            return False

    return True


def infer_workplace(posting: JobPosting) -> Workplace | None:
    """Best-effort workplace classification from normalized and raw fields."""
    raw = posting.raw
    if isinstance(raw, dict):
        for key in ("workplaceType", "workplace_type"):
            normalized = _normalize_workplace_token(str(raw.get(key, "")))
            if normalized:
                return normalized
        if raw.get("isRemote") is True:
            return "remote"

    for source in (posting.location, posting.title):
        normalized = _normalize_workplace_text(str(source))
        if normalized:
            return normalized
    return None


def _search_text(posting: JobPosting) -> str:
    return " ".join(
        part.lower() for part in (posting.title, posting.company, posting.location) if part
    )


def _terms(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip().lower()
        if not text:
            return []
        return [part for part in re.split(r"[\s,]+", text) if part]
    if isinstance(value, list):
        terms: list[str] = []
        for item in value:
            terms.extend(_terms(item))
        return terms
    return _terms(str(value))


def _workplace_terms(value: Any) -> set[Workplace]:
    terms: set[Workplace] = set()
    for token in _terms(value):
        normalized = _normalize_workplace_token(token)
        if normalized:
            terms.add(normalized)
    return terms


def _normalize_workplace_token(value: str) -> Workplace | None:
    token = value.strip().lower().replace("_", "-")
    if not token:
        return None
    if token in _WORKPLACE_ALIASES:
        return _WORKPLACE_ALIASES[token]
    if "remote" in token:
        return "remote"
    if "hybrid" in token:
        return "hybrid"
    if "onsite" in token or "on-site" in token or "on site" in token:
        return "onsite"
    return None


def _min_salary(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        rounded = int(round(value))
        return rounded if rounded > 0 else None
    if isinstance(value, str) and value.strip():
        try:
            rounded = int(round(float(value.replace(",", ""))))
        except ValueError:
            return None
        return rounded if rounded > 0 else None
    return None


def _salary_currency(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip().upper()
    return "USD"


def _normalize_workplace_text(value: str) -> Workplace | None:
    text = value.strip().lower()
    if not text:
        return None
    if re.search(r"\bremote\b", text):
        return "remote"
    if re.search(r"\bhybrid\b", text):
        return "hybrid"
    if re.search(r"\bon[- ]site\b", text):
        return "onsite"
    return None
