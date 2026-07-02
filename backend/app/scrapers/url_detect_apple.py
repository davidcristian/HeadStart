"""Apple Careers URL detection helpers."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs

from app.scrapers.url_detect_types import SourceDetection

_LOCALE_PATH_RE = re.compile(r"^/([a-z]{2}-[a-z]{2})(?:/|$)", re.IGNORECASE)


def detect_apple_careers(parsed: Any, host: str, page_title: str | None) -> SourceDetection | None:
    """Return adapter defaults when the URL matches Apple Careers."""
    if host not in {"jobs.apple.com", "www.jobs.apple.com"}:
        return None

    locale = "en-us"
    path_locale = _LOCALE_PATH_RE.match(parsed.path)
    if path_locale:
        locale = path_locale.group(1).lower()

    base_url = f"https://jobs.apple.com/{locale}/search"
    params = parse_qs(parsed.query, keep_blank_values=True)
    config: dict[str, Any] = {
        "company": "Apple",
        "portal_id": "apple",
        "locale": locale,
    }
    keyword = (params.get("search") or params.get("q") or params.get("query") or [""])[0].strip()
    location = (params.get("location") or [""])[0].strip()
    if keyword:
        config["search"] = keyword
    if location:
        config["location"] = location

    if "/details/" in parsed.path:
        return None

    return SourceDetection(
        adapter_key="apple_careers",
        suggested_name=_apple_suggested_name(keyword, location, page_title),
        base_url=base_url,
        default_config=config,
        query_url=parsed.geturl() if parsed.path.rstrip("/").endswith("/search") else base_url,
    )


def _apple_suggested_name(keyword: str, location: str, page_title: str | None) -> str:
    if page_title:
        cleaned = page_title.strip()
        for suffix in (
            " — Apple Careers",
            " - Apple Careers",
            " | Apple Careers",
            " Careers",
        ):
            if cleaned.endswith(suffix):
                cleaned = cleaned[: -len(suffix)].strip()
        if cleaned:
            return cleaned
    parts = [part for part in ("Apple", keyword, location) if part]
    return " / ".join(parts) if parts else "Apple Careers"
