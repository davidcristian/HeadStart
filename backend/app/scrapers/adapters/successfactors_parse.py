"""Parse helpers for SAP SuccessFactors Career Site Builder boards."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from app.scrapers.types import JobPosting, ScrapeContext

_CSRF_RE = re.compile(
    r'["\']?X-CSRF-Token["\']?\s*:\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_CATEGORY_RE = re.compile(r"/go/([^/\"'\s]+)/(\d+)", re.IGNORECASE)
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_DEFAULT_MAX_RESULTS = 1000
_MAX_RESULTS_CAP = 2000
_DEFAULT_LOCALE = "en_US"
_FIXED_PAGE_SIZE = 10
_CLOUD_HOST_SUFFIX = ".jobs.hr.cloud.sap"
_API_PATH = "/services/recruiting/v1/jobs"


@dataclass(frozen=True, slots=True)
class SuccessFactorsTarget:
    careers_base_url: str
    company: str
    locale: str
    keywords: str
    category_id: int | None


def resolve_target(ctx: ScrapeContext) -> SuccessFactorsTarget:
    """Resolve careers base URL + options from ``query_url`` / config."""
    base = str(ctx.config.get("careers_base_url") or "").strip().rstrip("/")
    if ctx.query_url:
        base = _base_from_url(ctx.query_url.strip()) or base
    if not base:
        raise ValueError(
            "successfactors scraper needs a query_url or config.careers_base_url "
            "(*.jobs.hr.cloud.sap career site or /services/recruiting/v1/jobs URL)"
        )
    parsed = urlparse(base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("successfactors careers_base_url must be an http(s) origin")
    base = f"{parsed.scheme}://{parsed.netloc.lower()}"
    company = str(ctx.config.get("company") or "").strip() or _company_from_host(parsed.netloc)
    locale = str(ctx.config.get("locale") or _DEFAULT_LOCALE).strip() or _DEFAULT_LOCALE
    category_id = _optional_category_id(ctx.config.get("category_id"))
    return SuccessFactorsTarget(
        careers_base_url=base,
        company=company,
        locale=locale,
        keywords=_keywords(ctx),
        category_id=category_id,
    )


def extract_csrf(html_text: str) -> str:
    """Pull the Career Site Builder CSRF token from seeded homepage HTML."""
    match = _CSRF_RE.search(html_text)
    if match is None:
        raise ValueError(
            "successfactors scraper could not find an X-CSRF-Token on the careers homepage"
        )
    token = match.group(1).strip()
    if not token:
        raise ValueError(
            "successfactors scraper found an empty X-CSRF-Token on the careers homepage"
        )
    return token


def extract_category_id(html_text: str, preferred: int | None = None) -> int:
    """Return ``preferred`` or the All-Jobs (else first) ``/go/<name>/<id>`` category."""
    if preferred is not None:
        return preferred
    categories = _CATEGORY_RE.findall(html_text)
    if not categories:
        raise ValueError(
            "successfactors scraper could not discover a categoryId from the careers homepage "
            "(set config.category_id)"
        )
    for name, raw_id in categories:
        if name.casefold().startswith("all"):
            return int(raw_id)
    return int(categories[0][1])


def extract_page(data: dict[str, Any]) -> tuple[list[dict[str, Any]], int | None]:
    """Return ``(job response dicts, totalJobs)`` from a jobs API payload."""
    raw_jobs = data.get("jobSearchResult")
    if raw_jobs is None:
        raw_jobs = []
    if not isinstance(raw_jobs, list):
        raise ValueError(
            "successfactors API returned unexpected jobSearchResult (expected a JSON array)"
        )
    jobs: list[dict[str, Any]] = []
    for item in raw_jobs:
        if not isinstance(item, dict):
            continue
        response = item.get("response")
        if isinstance(response, dict):
            jobs.append(response)
    total_raw = data.get("totalJobs")
    total: int | None
    if isinstance(total_raw, bool) or not isinstance(total_raw, int | float):
        total = None
    else:
        total = int(total_raw)
        if total < 0:
            total = None
    return jobs, total


def to_posting(raw: dict[str, Any], target: SuccessFactorsTarget) -> JobPosting | None:
    """Map one SuccessFactors job response object into a ``JobPosting``."""
    external_id = str(raw.get("id") or "").strip()
    title = str(raw.get("unifiedStandardTitle") or raw.get("title") or "").strip()
    if not external_id or not title:
        return None
    url_title = html.unescape(str(raw.get("urlTitle") or raw.get("unifiedUrlTitle") or "").strip())
    if url_title:
        url = f"{target.careers_base_url}/job/{url_title}/{external_id}-{target.locale}/"
    else:
        url = f"{target.careers_base_url}/job/{external_id}"
    return JobPosting(
        external_id=external_id,
        title=title,
        company=target.company,
        location=_location(raw),
        url=url,
        posted_at=_posted_at(raw),
        raw=raw,
    )


def max_results(config: dict[str, Any]) -> int:
    """Cap postings returned across pages."""
    raw = config.get("max_results", _DEFAULT_MAX_RESULTS)
    if not isinstance(raw, int | float) or isinstance(raw, bool):
        raise ValueError("max_results must be a positive integer")
    value = int(raw)
    if value <= 0:
        raise ValueError("max_results must be a positive integer")
    return min(value, _MAX_RESULTS_CAP)


def page_size() -> int:
    """Career Site Builder search pages are fixed at 10 jobs."""
    return _FIXED_PAGE_SIZE


def jobs_api_url(base: str) -> str:
    """Return the public recruiting jobs endpoint for a careers origin."""
    return f"{base.rstrip('/')}{_API_PATH}"


def _base_from_url(query_url: str) -> str:
    parsed = urlparse(query_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(
            "successfactors scraper query_url must be an http(s) careers or jobs API URL"
        )
    host = parsed.netloc.lower()
    path = parsed.path or ""
    if host.endswith(_CLOUD_HOST_SUFFIX) or host == "jobs.hr.cloud.sap":
        return f"{parsed.scheme}://{host}"
    if _API_PATH in path:
        return f"{parsed.scheme}://{host}"
    raise ValueError(
        "successfactors scraper query_url must be a *.jobs.hr.cloud.sap careers URL "
        "or a /services/recruiting/v1/jobs endpoint"
    )


def _company_from_host(host: str) -> str:
    cleaned = host.lower()
    if cleaned.endswith(_CLOUD_HOST_SUFFIX):
        slug = cleaned[: -len(_CLOUD_HOST_SUFFIX)]
        if "." in slug:
            slug = slug.split(".")[0]
        return _humanize_slug(slug) if slug else host
    return host


def _optional_category_id(raw: object) -> int | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool) or not isinstance(raw, int | float | str):
        raise ValueError("category_id must be a positive integer")
    try:
        value = int(str(raw).strip())
    except ValueError as exc:
        raise ValueError("category_id must be a positive integer") from exc
    if value <= 0:
        raise ValueError("category_id must be a positive integer")
    return value


def _keywords(ctx: ScrapeContext) -> str:
    for key in ("keywords", "q", "search", "search_text"):
        raw = ctx.config.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    filters = ctx.filters if isinstance(ctx.filters, dict) else {}
    for key in ("keywords", "q", "search"):
        raw = filters.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return ""


def _location(raw: dict[str, Any]) -> str:
    shorts = raw.get("jobLocationShort")
    if isinstance(shorts, list) and shorts:
        parts: list[str] = []
        seen: set[str] = set()
        for item in shorts:
            cleaned = _clean_location(item)
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                parts.append(cleaned)
        if parts:
            return "; ".join(parts)
    country = raw.get("jobLocationCountry")
    if isinstance(country, list) and country:
        first = str(country[0] or "").strip()
        if first:
            return first
    return ""


def _clean_location(value: object) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = _BR_RE.sub("", value)
    cleaned = html.unescape(cleaned).strip()
    return cleaned


def _posted_at(raw: dict[str, Any]) -> datetime | None:
    for key in ("unifiedStandardStart", "startDate", "postedDate"):
        value = raw.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        text = value.strip()
        for fmt in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(text, fmt)
            except ValueError:
                continue
            return parsed.replace(tzinfo=UTC)
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            continue
    return None


def _humanize_slug(slug: str) -> str:
    cleaned = slug.replace("-", " ").replace("_", " ").strip()
    return cleaned.title() if cleaned else slug
