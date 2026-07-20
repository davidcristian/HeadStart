"""Pure helpers for the Phenom People scraper."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from app.scrapers.dates import parse_iso8601
from app.scrapers.numbers import coerce_count
from app.scrapers.types import JobPosting, ScrapeContext

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
DEFAULT_MAX_RESULTS = 1000
MAX_RESULTS_CAP = 2000
DEFAULT_COUNTRY = "us"
DEFAULT_LOCALE = "en_us"
CSRF_RE = re.compile(r'"csrfToken"\s*:\s*"([^"]+)"')
REF_NUM_RE = re.compile(r'"refNum"\s*:\s*"([^"]+)"')
_OFFSET_RE = re.compile(r"([+-])(\d{2})(\d{2})$")


@dataclass(frozen=True, slots=True)
class PhenomSearchTarget:
    """Resolved Phenom careers site + search parameters."""

    careers_base_url: str
    company: str
    country: str
    locale: str
    ref_num: str
    keywords: str
    selected_fields: dict[str, list[str]]


def resolve_target(ctx: ScrapeContext) -> PhenomSearchTarget:
    """Build a search target from scrape context config / query URL."""
    company = str(ctx.config.get("company") or "").strip()
    country = str(ctx.config.get("country") or DEFAULT_COUNTRY).strip() or DEFAULT_COUNTRY
    locale = str(ctx.config.get("locale") or DEFAULT_LOCALE).strip() or DEFAULT_LOCALE
    ref_num = str(ctx.config.get("ref_num") or ctx.config.get("refNum") or "").strip()
    keywords = keywords_from_ctx(ctx)
    selected_fields = selected_fields_from_config(ctx.config)
    base = str(ctx.config.get("careers_base_url") or "").strip()
    if ctx.query_url:
        base, path_country, path_locale = base_from_url(ctx.query_url.strip())
        if path_country:
            country = path_country
        if path_locale:
            locale = path_locale
    if not base:
        raise ValueError("phenom scraper needs a query_url or config.careers_base_url")
    return PhenomSearchTarget(
        careers_base_url=base.rstrip("/"),
        company=company,
        country=country.lower(),
        locale=locale,
        ref_num=ref_num,
        keywords=keywords,
        selected_fields=selected_fields,
    )


def base_from_url(query_url: str) -> tuple[str, str, str]:
    """Extract careers origin and optional country/locale from a careers URL."""
    parsed = urlparse(query_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("phenom scraper query_url must be an http(s) careers site URL")
    base = f"{parsed.scheme}://{parsed.netloc.lower()}"
    parts = [part for part in parsed.path.split("/") if part]
    country = ""
    locale = ""
    if len(parts) >= 2 and parts[0] and parts[1]:
        country = parts[0].lower()
        lang = parts[1].lower()
        if "_" in lang:
            locale = lang
        elif country == "global":
            locale = f"{lang}_global"
        else:
            locale = f"{lang}_{country}"
    return base, country, locale


def search_results_url(target: PhenomSearchTarget) -> str:
    """Build the CSRF-seeding search-results page URL for a tenant."""
    lang = target.locale.split("_", 1)[0] or "en"
    return f"{target.careers_base_url}/{target.country}/{lang}/search-results"


def keywords_from_ctx(ctx: ScrapeContext) -> str:
    """Read optional keyword filter from config or search filters."""
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


def selected_fields_from_config(config: dict[str, Any]) -> dict[str, list[str]]:
    """Validate optional facet filters for the refineSearch payload."""
    raw = config.get("selected_fields")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("selected_fields must be an object mapping field -> string list")
    out: dict[str, list[str]] = {}
    for key, values in raw.items():
        field = str(key).strip()
        if not field:
            continue
        if not isinstance(values, list):
            raise ValueError("selected_fields values must be lists of strings")
        cleaned = [str(v).strip() for v in values if str(v).strip()]
        if cleaned:
            out[field] = cleaned
    return out


def page_size(config: dict[str, Any]) -> int:
    """Clamp page size to Phenom's accepted range."""
    raw = config.get("page_size", DEFAULT_PAGE_SIZE)
    if not isinstance(raw, int | float) or isinstance(raw, bool):
        raise ValueError("page_size must be a positive integer")
    size = int(raw)
    if size <= 0:
        raise ValueError("page_size must be a positive integer")
    return min(size, MAX_PAGE_SIZE)


def max_results(config: dict[str, Any]) -> int:
    """Clamp the cross-page result cap."""
    raw = config.get("max_results", DEFAULT_MAX_RESULTS)
    if not isinstance(raw, int | float) or isinstance(raw, bool):
        raise ValueError("max_results must be a positive integer")
    value = int(raw)
    if value <= 0:
        raise ValueError("max_results must be a positive integer")
    return min(value, MAX_RESULTS_CAP)


def extract_page(data: dict[str, Any]) -> tuple[list[Any], int | None]:
    """Pull jobs + totalHits from a refineSearch response body."""
    rs = data.get("refineSearch")
    if not isinstance(rs, dict):
        raise ValueError("phenom API returned unexpected refineSearch field")
    jobs: list[Any] | None = None
    inner = rs.get("data")
    if isinstance(inner, dict) and isinstance(inner.get("jobs"), list):
        jobs = inner["jobs"]
    elif isinstance(rs.get("jobs"), list):
        jobs = rs["jobs"]
    if jobs is None:
        raise ValueError("phenom API returned unexpected jobs field (expected a JSON array)")
    total: int | None = None
    for candidate in (
        rs.get("totalHits"),
        inner.get("totalHits") if isinstance(inner, dict) else None,
    ):
        if candidate is not None:
            total = coerce_count(candidate, len(jobs))
            break
    return jobs, total


def to_posting(raw: object, target: PhenomSearchTarget) -> JobPosting | None:
    """Normalize one Phenom job object into a JobPosting."""
    if not isinstance(raw, dict):
        return None
    external_id = str(raw.get("jobSeqNo") or raw.get("jobId") or raw.get("reqId") or "").strip()
    title = str(raw.get("title") or "").strip()
    if not external_id or not title:
        return None
    company = target.company or str(raw.get("company") or "").strip() or "Unknown"
    job_path_id = str(raw.get("jobSeqNo") or raw.get("jobId") or external_id).strip()
    lang = target.locale.split("_", 1)[0] or "en"
    url = f"{target.careers_base_url}/{target.country}/{lang}/job/{job_path_id}"
    return JobPosting(
        external_id=external_id,
        title=title,
        company=company,
        location=location_from_job(raw),
        url=url,
        posted_at=posted_at(raw.get("postedDate") or raw.get("dateCreated")),
        raw=raw,
    )


def location_from_job(data: dict[str, Any]) -> str:
    """Prefer Phenom's combined location fields, then city/state/country parts."""
    for key in ("location", "cityStateCountry", "cityState"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    parts = [
        str(data.get(key) or "").strip()
        for key in ("city", "state", "country")
        if str(data.get(key) or "").strip()
    ]
    return ", ".join(parts)


def posted_at(value: object) -> datetime | None:
    """Parse Phenom timestamps, including offsets like ``+0000``."""
    if not isinstance(value, str) or not value:
        return None
    normalized = _OFFSET_RE.sub(r"\1\2:\3", value.strip())
    return parse_iso8601(normalized)


def parse_session_html(html: str) -> tuple[str | None, str]:
    """Extract CSRF token and optional refNum from a search-results HTML page."""
    csrf: str | None = None
    match = CSRF_RE.search(html)
    if match:
        csrf = match.group(1)
    ref_match = REF_NUM_RE.search(html)
    ref_num = ref_match.group(1).strip() if ref_match else ""
    return csrf, ref_num
