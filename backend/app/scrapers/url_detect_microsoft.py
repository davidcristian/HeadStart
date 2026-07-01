"""Microsoft Careers URL detection helpers."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs

from app.scrapers.url_detect_types import SourceDetection


def detect_microsoft_careers(
    parsed: Any, host: str, page_title: str | None
) -> SourceDetection | None:
    """Return adapter defaults when the URL matches Microsoft Careers."""
    if not host.endswith("careers.microsoft.com"):
        return None

    base_url = "https://apply.careers.microsoft.com/careers"
    params = parse_qs(parsed.query, keep_blank_values=True)
    config: dict[str, Any] = {
        "company": "Microsoft",
        "portal_id": "microsoft",
        "domain": "microsoft.com",
    }
    keyword = (params.get("q") or params.get("query") or [""])[0].strip()
    location = (params.get("location") or params.get("l") or [""])[0].strip()
    if keyword:
        config["q"] = keyword
    if location:
        config["location"] = location

    if parsed.path.startswith("/api/pcsx/search"):
        api_params = parse_qs(parsed.query, keep_blank_values=True)
        domain = (api_params.get("domain") or [config["domain"]])[0].strip()
        if domain:
            config["domain"] = domain
        keyword = (api_params.get("query") or api_params.get("q") or [keyword])[0].strip()
        if keyword:
            config["q"] = keyword
        location = (api_params.get("location") or [location])[0].strip()
        if location:
            config["location"] = location

    return SourceDetection(
        adapter_key="microsoft_careers",
        suggested_name=_microsoft_suggested_name(keyword, location, page_title),
        base_url=base_url,
        default_config=config,
        query_url=parsed.geturl() if parsed.path.startswith("/api/") else base_url,
    )


def _microsoft_suggested_name(keyword: str, location: str, page_title: str | None) -> str:
    if page_title:
        cleaned = page_title.strip()
        for suffix in (
            " — Microsoft Careers",
            " - Microsoft Careers",
            " | Microsoft Careers",
            " Careers",
        ):
            if cleaned.endswith(suffix):
                cleaned = cleaned[: -len(suffix)].strip()
        if cleaned:
            return cleaned
    parts = [part for part in ("Microsoft", keyword, location) if part]
    return " / ".join(parts) if parts else "Microsoft Careers"
