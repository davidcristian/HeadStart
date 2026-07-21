"""Map a careers-page URL to a scraper adapter and source defaults."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from app.scrapers.adapters.ashby_parse import encode_board_slug
from app.scrapers.adapters.workday_parse import board_from_url, try_parse_host
from app.scrapers.url_detect_amazon import detect_amazon_jobs
from app.scrapers.url_detect_apple import detect_apple_careers
from app.scrapers.url_detect_ibm import detect_ibm_careers
from app.scrapers.url_detect_icims import detect_icims
from app.scrapers.url_detect_indeed import detect_indeed
from app.scrapers.url_detect_meta import detect_meta_careers
from app.scrapers.url_detect_microsoft import detect_microsoft_careers
from app.scrapers.url_detect_phenom import detect_phenom
from app.scrapers.url_detect_rippling import detect_rippling
from app.scrapers.url_detect_shopify import detect_shopify_careers
from app.scrapers.url_detect_smartrecruiters import detect_smartrecruiters
from app.scrapers.url_detect_snowflake import detect_snowflake_careers
from app.scrapers.url_detect_types import SourceDetection
from app.scrapers.url_detect_uber import detect_uber_careers
from app.scrapers.url_detect_workable import detect_workable

# Snap's marketing careers site links into Workday myworkdaysite.com.
_WORKDAY_KNOWN_VANITY: dict[str, dict[str, str]] = {
    "careers.snap.com": {
        "tenant": "snapchat",
        "site": "snap",
        "region": "wd1",
        "company": "Snap",
        "host_kind": "site",
    },
}


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
        detect_smartrecruiters,
        _detect_workday,
        _detect_google_careers,
        detect_microsoft_careers,
        detect_amazon_jobs,
        detect_apple_careers,
        detect_meta_careers,
        detect_shopify_careers,
        detect_uber_careers,
        detect_snowflake_careers,
        detect_icims,
        detect_phenom,
        detect_rippling,
        detect_ibm_careers,
        detect_workable,
        detect_indeed,
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
    # Jobs board host, or Ashby-owned API host with the posting-api path
    # (never match arbitrary hosts that merely contain that path substring).
    is_jobs_host = host == "jobs.ashbyhq.com"
    is_api_path = host.endswith(".ashbyhq.com") and "posting-api/job-board" in parsed.path
    if not is_jobs_host and not is_api_path:
        return None

    board = ""
    if is_jobs_host:
        parts = [part for part in parsed.path.split("/") if part]
        board = parts[0] if parts else ""
    else:
        parts = [part for part in parsed.path.split("/") if part]
        idx = parts.index("job-board") if "job-board" in parts else -1
        if idx >= 0 and idx + 1 < len(parts):
            board = parts[idx + 1]
    if not board:
        return None

    board = unquote(board)
    company = _humanize_slug(board)
    suggested_name = _title_or_slug(page_title, company)
    encoded = encode_board_slug(board)
    base_url = f"https://jobs.ashbyhq.com/{encoded}"
    return SourceDetection(
        adapter_key="ashby",
        suggested_name=suggested_name,
        base_url=base_url,
        default_config={"board": board, "company": company},
        query_url=base_url,
    )


def _detect_workday(parsed: Any, host: str, page_title: str | None) -> SourceDetection | None:
    vanity = _WORKDAY_KNOWN_VANITY.get(host)
    if vanity is not None:
        tenant = vanity["tenant"]
        site = vanity["site"]
        region = vanity["region"]
        company = vanity["company"]
        host_kind = vanity["host_kind"]
        board_host = f"{region}.myworkdaysite.com"
        base_url = f"https://{board_host}/recruiting/{tenant}/{site}"
        config: dict[str, Any] = {
            "tenant": tenant,
            "site": site,
            "region": region,
            "company": company,
            "locale": "en-US",
            "host_kind": host_kind,
        }
        return SourceDetection(
            adapter_key="workday",
            suggested_name=_title_or_slug(page_title, company),
            base_url=base_url,
            default_config=config,
            query_url=base_url,
        )

    if try_parse_host(host) is None:
        return None
    try:
        board = board_from_url(f"{parsed.scheme}://{host}{parsed.path}")
    except ValueError:
        return None

    company = _humanize_slug(board.tenant)
    suggested_name = _title_or_slug(page_title, company)
    config = {
        "tenant": board.tenant,
        "site": board.site,
        "company": company,
        "locale": board.locale,
        "host_kind": board.host_kind,
    }
    if board.region:
        config["region"] = board.region
    base_url = board.board_url
    return SourceDetection(
        adapter_key="workday",
        suggested_name=suggested_name,
        base_url=base_url,
        default_config=config,
        query_url=base_url,
    )


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


def _title_or_slug(page_title: str | None, fallback: str) -> str:
    if not page_title:
        return fallback
    cleaned = page_title.strip()
    for suffix in (" Careers", " Jobs", " Job Board", " | Careers", " - Careers"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
    return cleaned or fallback
