"""Pure helpers for the IBM Careers (www-api.ibm.com search) scraper."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.scrapers.dates import parse_iso8601
from app.scrapers.numbers import coerce_count
from app.scrapers.types import JobPosting, ScrapeContext

DEFAULT_APP_ID = "careers"
DEFAULT_SCOPE = "careers2"
DEFAULT_COMPANY = "IBM"
DEFAULT_QUERY = "*"
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
DEFAULT_MAX_RESULTS = 1000
MAX_RESULTS_CAP = 2000
API_HOST = "www-api.ibm.com"
API_PATH_PREFIX = "/search/api/v1-1/ibmcom/appid/"


@dataclass(frozen=True, slots=True)
class IbmCareersTarget:
    """Resolved IBM Careers search parameters."""

    app_id: str
    scope: str
    query: str
    company: str


def resolve_target(ctx: ScrapeContext) -> IbmCareersTarget:
    """Build a search target from scrape context config / query URL."""
    app_id = str(ctx.config.get("app_id") or ctx.config.get("appid") or DEFAULT_APP_ID).strip()
    scope = str(ctx.config.get("scope") or DEFAULT_SCOPE).strip() or DEFAULT_SCOPE
    company = str(ctx.config.get("company") or "").strip() or DEFAULT_COMPANY
    query = keywords_from_ctx(ctx)
    if ctx.query_url:
        from_url = target_from_url(ctx.query_url.strip())
        app_id = from_url.app_id or app_id
        scope = from_url.scope or scope
        if from_url.query:
            query = from_url.query
        # Prefer explicit config company over URL defaults (IBM marketing host).
        if not str(ctx.config.get("company") or "").strip() and from_url.company:
            company = from_url.company
    app_id = app_id or DEFAULT_APP_ID
    query = query.strip() or DEFAULT_QUERY
    return IbmCareersTarget(app_id=app_id, scope=scope, query=query, company=company)


def target_from_url(query_url: str) -> IbmCareersTarget:
    """Extract app_id / scope / query from an IBM careers or API URL."""
    parsed = urlparse(query_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("ibm_careers scraper query_url must be an http(s) URL")
    host = parsed.netloc.lower()
    params = parse_qs(parsed.query)
    query = _first_param(params, "query", "q", "keywords", "search")
    scope = _first_param(params, "scope", "scopeid") or ""
    app_id = _first_param(params, "appid", "app_id", "appId") or ""
    company = ""

    if host == API_HOST:
        parsed_app = _app_id_from_api_path(parsed.path)
        if not parsed_app:
            raise ValueError("ibm_careers scraper could not determine app_id from API query_url")
        app_id = parsed_app or app_id
    elif host in {"www.ibm.com", "ibm.com"} and "/careers" in parsed.path.lower():
        app_id = app_id or DEFAULT_APP_ID
        scope = scope or DEFAULT_SCOPE
        company = DEFAULT_COMPANY
    elif host == "careers.ibm.com":
        app_id = app_id or DEFAULT_APP_ID
        scope = scope or DEFAULT_SCOPE
        company = DEFAULT_COMPANY
    else:
        raise ValueError("ibm_careers scraper query_url must be an IBM careers or search API URL")

    return IbmCareersTarget(
        app_id=app_id or DEFAULT_APP_ID,
        scope=scope or DEFAULT_SCOPE,
        query=query,
        company=company,
    )


def _app_id_from_api_path(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    # search/api/v1-1/ibmcom/appid/<appid>/responseFormat/json
    if len(parts) >= 6 and "/".join(parts[:5]) == "search/api/v1-1/ibmcom/appid":
        return parts[5]
    return ""


def _first_param(params: dict[str, list[str]], *keys: str) -> str:
    for key in keys:
        values = params.get(key) or []
        if values and str(values[0]).strip():
            return str(values[0]).strip()
    return ""


def keywords_from_ctx(ctx: ScrapeContext) -> str:
    """Resolve the IBM search query from config or scrape filters."""
    for key in ("keywords", "query", "q", "search"):
        value = ctx.config.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    for key in ("keywords", "query", "q", "search"):
        value = ctx.filters.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def page_size(config: dict[str, Any]) -> int:
    """Jobs per API page (clamped)."""
    raw = config.get("page_size")
    size = coerce_count(raw, default=DEFAULT_PAGE_SIZE)
    if size < 1:
        size = DEFAULT_PAGE_SIZE
    return min(size, MAX_PAGE_SIZE)


def max_results(config: dict[str, Any]) -> int:
    """Cap across pages (clamped)."""
    raw = config.get("max_results")
    limit = coerce_count(raw, default=DEFAULT_MAX_RESULTS)
    if limit < 1:
        limit = DEFAULT_MAX_RESULTS
    return min(limit, MAX_RESULTS_CAP)


def search_api_url(target: IbmCareersTarget, *, offset: int, page_size: int) -> str:
    """Build the public Falcon search URL for one page."""
    page = (offset // page_size) + 1 if page_size > 0 else 1
    from urllib.parse import quote, urlencode

    base = (
        f"https://{API_HOST}{API_PATH_PREFIX}"
        f"{quote(target.app_id, safe='')}/responseFormat/json"
    )
    query = urlencode(
        {
            "scope": target.scope,
            "rmdt": "ALL",
            "appid": target.app_id,
            "query": target.query,
            "nr": page_size,
            "fr": max(offset, 0),
            "page": max(page, 1),
        }
    )
    return f"{base}?{query}"


def extract_page(data: Any) -> tuple[list[dict[str, Any]], int | None]:
    """Return hit dicts and total count from an IBM search payload."""
    if not isinstance(data, dict):
        return [], None
    resultset = data.get("resultset")
    if not isinstance(resultset, dict):
        return [], None
    searchresults = resultset.get("searchresults")
    if not isinstance(searchresults, dict):
        return [], None
    total = coerce_count(searchresults.get("totalresults"), default=-1)
    total_or_none: int | None = None if total < 0 else total
    hits = searchresults.get("searchresultlist")
    if isinstance(hits, dict):
        hits = [hits]
    if not isinstance(hits, list):
        return [], total_or_none
    return [hit for hit in hits if isinstance(hit, dict)], total_or_none


def to_posting(raw: dict[str, Any], target: IbmCareersTarget) -> JobPosting | None:
    """Normalize one IBM search hit into a ``JobPosting``."""
    attrs = _doc_attrs(raw)
    title = str(raw.get("title") or attrs.get("title") or "").strip()
    if not title:
        return None
    job_id = str(attrs.get("field_text_01") or "").strip()
    external_id = job_id or str(raw.get("id") or "").strip()
    if not external_id:
        return None
    url = str(raw.get("url") or attrs.get("url") or "").strip()
    if job_id and not url:
        url = f"https://careers.ibm.com/careers/JobDetail?jobId={job_id}"
    location = str(attrs.get("field_keyword_19") or attrs.get("field_keyword_05") or "").strip()
    posted_at = _posted_at(attrs)
    return JobPosting(
        external_id=external_id,
        title=title,
        company=target.company,
        location=location,
        url=url,
        posted_at=posted_at,
        raw=raw,
    )


def _doc_attrs(raw: dict[str, Any]) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    for item in raw.get("docattributes") or []:
        if not isinstance(item, dict) or not item:
            continue
        key = next(iter(item))
        attrs[str(key)] = item[key]
    return attrs


def _posted_at(attrs: dict[str, Any]) -> datetime | None:
    for key in ("dcdate", "effectivedate", "processedtime"):
        value = attrs.get(key)
        if isinstance(value, str) and value and "T" not in value:
            # Date-only values from Falcon (YYYY-MM-DD).
            parsed = parse_iso8601(f"{value}T00:00:00+00:00")
            if parsed is not None:
                return parsed
        parsed = parse_iso8601(value)
        if parsed is not None:
            return parsed
    return None
