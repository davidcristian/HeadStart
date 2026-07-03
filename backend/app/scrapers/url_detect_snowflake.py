"""Snowflake Careers URL detection helpers."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs

from app.scrapers.url_detect_types import SourceDetection

_HOST_RE = re.compile(r"^careers\.snowflake\.com$", re.IGNORECASE)
_SEARCH_PATH_RE = re.compile(r"^/(?:[a-z]{2}/[a-z]{2}/)?search-results/?$", re.IGNORECASE)


def detect_snowflake_careers(
    parsed: Any, host: str, page_title: str | None
) -> SourceDetection | None:
    """Return adapter defaults when the URL matches Snowflake Careers."""
    if not _HOST_RE.match(host):
        return None
    if parsed.path in {"", "/"}:
        pass
    elif not _SEARCH_PATH_RE.match(parsed.path):
        return None

    base_url = "https://careers.snowflake.com/us/en/search-results"
    params = parse_qs(parsed.query, keep_blank_values=True)
    config: dict[str, Any] = {
        "company": "Snowflake",
        "portal_id": "snowflake",
        "board": "snowflake",
    }
    keyword = (params.get("q") or params.get("search") or params.get("keywords") or [""])[0].strip()
    if keyword:
        config["q"] = keyword

    return SourceDetection(
        adapter_key="snowflake_careers",
        suggested_name=_snowflake_suggested_name(keyword, page_title),
        base_url=base_url,
        default_config=config,
        query_url=base_url,
    )


def _snowflake_suggested_name(keyword: str, page_title: str | None) -> str:
    if page_title:
        cleaned = page_title.strip()
        for suffix in (
            " | Snowflake Careers",
            " - Snowflake Careers",
            " | Snowflake",
            " Careers",
        ):
            if cleaned.endswith(suffix):
                cleaned = cleaned[: -len(suffix)].strip()
        if cleaned:
            return cleaned
    return "Snowflake / " + keyword if keyword else "Snowflake Careers"
