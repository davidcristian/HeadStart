"""Meta Careers URL detection helpers."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs

from app.scrapers.url_detect_types import SourceDetection

_HOST_RE = re.compile(
    r"^(?:www\.)?(?:metacareers|facebookcareers)\.com$",
    re.IGNORECASE,
)


def detect_meta_careers(parsed: Any, host: str, page_title: str | None) -> SourceDetection | None:
    """Return adapter defaults when the URL matches Meta Careers."""
    if not _HOST_RE.match(host):
        return None

    path = parsed.path.rstrip("/") or "/"
    if path.startswith("/jobs/") and path.count("/") >= 2:
        return None

    params = parse_qs(parsed.query, keep_blank_values=True)
    config: dict[str, Any] = {"company": "Meta", "portal_id": "meta"}
    keyword = (params.get("q") or params.get("query") or [""])[0].strip()
    if keyword:
        config["q"] = keyword

    base_url = "https://www.metacareers.com/jobsearch/"
    return SourceDetection(
        adapter_key="meta_careers",
        suggested_name=_meta_suggested_name(keyword, page_title),
        base_url=base_url,
        default_config=config,
        query_url=parsed.geturl(),
    )


def _meta_suggested_name(keyword: str, page_title: str | None) -> str:
    if page_title:
        cleaned = page_title.strip()
        for suffix in (
            " | Meta Careers",
            " - Meta Careers",
            " — Meta Careers",
            " Careers",
            " Jobs",
        ):
            if cleaned.endswith(suffix):
                cleaned = cleaned[: -len(suffix)].strip()
        if cleaned:
            return cleaned
    parts = [part for part in ("Meta", keyword) if part]
    return " / ".join(parts) if parts else "Meta Careers"
