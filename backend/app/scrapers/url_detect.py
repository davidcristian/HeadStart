"""Map a careers-page URL to a scraper adapter and source defaults."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.scrapers.url_detect_amazon import detect_amazon_jobs
from app.scrapers.url_detect_apple import detect_apple_careers
from app.scrapers.url_detect_meta import detect_meta_careers
from app.scrapers.url_detect_microsoft import detect_microsoft_careers
from app.scrapers.url_detect_types import SourceDetection

_LOCALE_RE = re.compile(r"^[a-z]{2}-[A-Z]{2}$")
_WORKDAY_HOST_WITH_REGION = re.compile(r"^([^.]+)\.(wd\d+)\.myworkdayjobs\.com$", re.IGNORECASE)
_WORKDAY_HOST_PLAIN = re.compile(r"^([^.]+)\.myworkdayjobs\.com$", re.IGNORECASE)


def detect_source_from_url(url: str, *, page_title: str | None = None) -> SourceDetection | None:
    """Return adapter defaults when the URL matches a known public job board."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    host = parsed.netloc.lower()
    for detector in (
        _detect_greenhouse,
        _detect_lever,
        _detect_ashby,
        _detect_workday,
        _detect_google_careers,
        detect_microsoft_careers,
        detect_amazon_jobs,
        detect_apple_careers,
        detect_meta_careers,
        _detect_indeed,
    ):
        result = detector(parsed, host, page_title)
        if result is not None:
            return result
    return None


def _humanize_slug(slug: str) -> str:
    cleaned = slug.replace("-", " ").replace("_", " ").strip()
    return cleaned.title() if cleaned else slug


def _detect_greenhouse(parsed: Any, host: str, page_title: str | None) -> SourceDetection | None:
    token = ""
    if host == "boards-api.greenhouse.io":
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 3 and parts[0] == "v1" and parts[1] == "boards":
            token = parts[2]
    elif host in {"boards.greenhouse.io", "job-boards.greenhouse.io"}:
        parts = [part for part in parsed.path.split("/") if part]
        if parts and parts[0] != "jobs":
            token = parts[0]
        elif len(parts) >= 2 and parts[0] == "jobs":
            token = parts[1]
    if not token:
        return None

    company = _humanize_slug(token)
    suggested_name = _title_or_slug(page_title, company)
    base_url = f"https://boards.greenhouse.io/{token}"
    return SourceDetection(
        adapter_key="greenhouse",
        suggested_name=suggested_name,
        base_url=base_url,
        default_config={"board_token": token, "company": company},
        query_url=base_url,
    )


def _detect_lever(parsed: Any, host: str, page_title: str | None) -> SourceDetection | None:
    if not (host.startswith("jobs.") and host.endswith(".lever.co")):
        return None
    region = "eu" if host.startswith("jobs.eu.") else "global"
    parts = [part for part in parsed.path.split("/") if part]
    site = parts[0] if parts else ""
    if not site:
        return None

    company = _humanize_slug(site)
    suggested_name = _title_or_slug(page_title, company)
    base_url = f"https://{host}/{site}"
    config: dict[str, Any] = {"site": site, "company": company}
    if region == "eu":
        config["region"] = "eu"
    return SourceDetection(
        adapter_key="lever",
        suggested_name=suggested_name,
        base_url=base_url,
        default_config=config,
        query_url=base_url,
    )


def _detect_ashby(parsed: Any, host: str, page_title: str | None) -> SourceDetection | None:
    if host != "jobs.ashbyhq.com" and "posting-api/job-board" not in parsed.path:
        return None

    board = ""
    if host == "jobs.ashbyhq.com":
        parts = [part for part in parsed.path.split("/") if part]
        board = parts[0] if parts else ""
    else:
        parts = [part for part in parsed.path.split("/") if part]
        idx = parts.index("job-board") if "job-board" in parts else -1
        if idx >= 0 and idx + 1 < len(parts):
            board = parts[idx + 1]
    if not board:
        return None

    company = _humanize_slug(board)
    suggested_name = _title_or_slug(page_title, company)
    base_url = f"https://jobs.ashbyhq.com/{board}"
    return SourceDetection(
        adapter_key="ashby",
        suggested_name=suggested_name,
        base_url=base_url,
        default_config={"board": board, "company": company},
        query_url=base_url,
    )


def _detect_workday(parsed: Any, host: str, page_title: str | None) -> SourceDetection | None:
    tenant, region = _parse_workday_host(host)
    if not tenant:
        return None

    parts = [part for part in parsed.path.split("/") if part]
    locale = "en-US"
    if parts and _LOCALE_RE.match(parts[0]):
        locale = parts[0]
        parts = parts[1:]

    site = ""
    if len(parts) >= 4 and parts[0] == "wday" and parts[1] == "cxs":
        tenant = parts[2] or tenant
        site = parts[3]
    elif parts:
        site = parts[0]
    if not site:
        return None

    company = _humanize_slug(tenant)
    suggested_name = _title_or_slug(page_title, company)
    board_host = _workday_host(tenant, region)
    base_url = f"https://{board_host}/{locale}/{site}"
    config: dict[str, Any] = {"tenant": tenant, "site": site, "company": company, "locale": locale}
    if region:
        config["region"] = region
    return SourceDetection(
        adapter_key="workday",
        suggested_name=suggested_name,
        base_url=base_url,
        default_config=config,
        query_url=base_url,
    )


def _parse_workday_host(host: str) -> tuple[str, str | None]:
    match = _WORKDAY_HOST_WITH_REGION.match(host)
    if match:
        return match.group(1), match.group(2)
    match = _WORKDAY_HOST_PLAIN.match(host)
    if match:
        return match.group(1), None
    return "", None


def _workday_host(tenant: str, region: str | None) -> str:
    if region:
        return f"{tenant}.{region}.myworkdayjobs.com"
    return f"{tenant}.myworkdayjobs.com"


def _detect_google_careers(
    parsed: Any, host: str, page_title: str | None
) -> SourceDetection | None:
    if host == "careers.google.com":
        base_url = "https://www.google.com/about/careers/applications/jobs/results/"
        return SourceDetection(
            adapter_key="google_careers",
            suggested_name=_title_or_slug(page_title, "Google"),
            base_url=base_url,
            default_config={"company": "Google", "portal_id": "google"},
            query_url=base_url,
        )

    if host not in {"www.google.com", "google.com"}:
        return None
    path = parsed.path.rstrip("/")
    if not path.endswith("/about/careers/applications/jobs/results"):
        return None

    params = parse_qs(parsed.query, keep_blank_values=True)
    config: dict[str, Any] = {"company": "Google", "portal_id": "google"}
    keyword = (params.get("q") or [""])[0].strip()
    location = (params.get("location") or [""])[0].strip()
    if keyword:
        config["q"] = keyword
    if location:
        config["location"] = location

    base_url = "https://www.google.com/about/careers/applications/jobs/results/"
    return SourceDetection(
        adapter_key="google_careers",
        suggested_name=_google_suggested_name(keyword, location, page_title),
        base_url=base_url,
        default_config=config,
        query_url=parsed.geturl(),
    )


def _google_suggested_name(keyword: str, location: str, page_title: str | None) -> str:
    if page_title:
        cleaned = page_title.strip()
        for suffix in (
            " — Google Careers",
            " - Google Careers",
            " | Google Careers",
            " Careers",
        ):
            if cleaned.endswith(suffix):
                cleaned = cleaned[: -len(suffix)].strip()
        if cleaned:
            return cleaned
    parts = [part for part in ("Google", keyword, location) if part]
    return " / ".join(parts) if parts else "Google Careers"


def _detect_indeed(parsed: Any, host: str, page_title: str | None) -> SourceDetection | None:
    if not host.endswith(".indeed.com") and host != "indeed.com":
        return None
    path = parsed.path.rstrip("/") or "/"
    if not path.startswith("/jobs"):
        return None

    params = parse_qs(parsed.query, keep_blank_values=True)
    keyword = (params.get("q") or [""])[0].strip()
    location = (params.get("l") or [""])[0].strip()
    suggested = _indeed_suggested_name(keyword, location, page_title)
    base_url = f"{parsed.scheme}://{parsed.netloc}/jobs"
    config: dict[str, Any] = {}
    if keyword:
        config["q"] = keyword
    if location:
        config["l"] = location
    return SourceDetection(
        adapter_key="indeed",
        suggested_name=suggested,
        base_url=base_url,
        default_config=config,
        query_url=parsed.geturl(),
    )


def _indeed_suggested_name(keyword: str, location: str, page_title: str | None) -> str:
    if page_title:
        cleaned = page_title.strip()
        for suffix in (
            " | Indeed.com",
            " | Indeed",
            " Jobs, Employment | Indeed",
            " Jobs | Indeed",
        ):
            if cleaned.endswith(suffix):
                cleaned = cleaned[: -len(suffix)].strip()
        if cleaned:
            return cleaned
    parts = [part for part in (keyword, location) if part]
    if parts:
        return "Indeed: " + " / ".join(parts)
    return "Indeed Search"


def _title_or_slug(page_title: str | None, fallback: str) -> str:
    if not page_title:
        return fallback
    cleaned = page_title.strip()
    for suffix in (" Careers", " Jobs", " Job Board", " | Careers", " - Careers"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
    return cleaned or fallback
