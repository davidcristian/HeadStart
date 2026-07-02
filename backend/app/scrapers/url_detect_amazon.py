"""Amazon Jobs URL detection helpers."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs

from app.scrapers.url_detect_types import SourceDetection

_HOST_RE = re.compile(r"^(?:www\.)?amazon\.jobs$", re.IGNORECASE)
_LOCALE_PATH_RE = re.compile(r"^/([a-z]{2})(?:/|$)", re.IGNORECASE)


def detect_amazon_jobs(parsed: Any, host: str, page_title: str | None) -> SourceDetection | None:
    """Return adapter defaults when the URL matches amazon.jobs."""
    if not _HOST_RE.match(host):
        return None

    locale = "en"
    locale_match = _LOCALE_PATH_RE.match(parsed.path)
    if locale_match:
        locale = locale_match.group(1)

    params = parse_qs(parsed.query, keep_blank_values=True)
    config: dict[str, Any] = {"company": "Amazon", "portal_id": "amazon", "locale": locale}
    keyword = (params.get("base_query") or params.get("q") or [""])[0].strip()
    location = (params.get("loc_query") or params.get("location") or [""])[0].strip()
    country = (params.get("country") or [""])[0].strip()
    if keyword:
        config["base_query"] = keyword
    if location:
        config["loc_query"] = location
    if country:
        config["country"] = country

    base_url = f"https://www.amazon.jobs/{locale}/search"
    return SourceDetection(
        adapter_key="amazon_jobs",
        suggested_name=_amazon_suggested_name(keyword, location, page_title),
        base_url=base_url,
        default_config=config,
        query_url=parsed.geturl(),
    )


def _amazon_suggested_name(keyword: str, location: str, page_title: str | None) -> str:
    if page_title:
        cleaned = page_title.strip()
        for suffix in (
            " | Amazon.jobs",
            " - Amazon.jobs",
            " — Amazon.jobs",
            " Careers",
            " Jobs",
        ):
            if cleaned.endswith(suffix):
                cleaned = cleaned[: -len(suffix)].strip()
        if cleaned:
            return cleaned
    parts = [part for part in ("Amazon", keyword, location) if part]
    return " / ".join(parts) if parts else "Amazon Jobs"
