"""Indeed URL detection helpers."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs

from app.scrapers.url_detect_types import SourceDetection


def detect_indeed(parsed: Any, host: str, page_title: str | None) -> SourceDetection | None:
    """Return adapter defaults when the URL matches an Indeed jobs search page."""
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
