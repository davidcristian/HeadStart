"""IBM Careers URL detection helpers."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs

from app.scrapers.url_detect_types import SourceDetection

_DEFAULT_APP_ID = "careers"
_DEFAULT_SCOPE = "careers2"


def detect_ibm_careers(parsed: Any, host: str, page_title: str | None) -> SourceDetection | None:
    """Return adapter defaults when the URL matches IBM Careers search or API."""
    params = parse_qs(parsed.query)
    query = _first(params, "query", "q", "keywords", "search")
    scope = _first(params, "scope", "scopeid") or _DEFAULT_SCOPE
    app_id = _first(params, "appid", "app_id", "appId") or _DEFAULT_APP_ID
    path = (parsed.path or "").lower()

    if host == "www-api.ibm.com":
        parts = [part for part in path.split("/") if part]
        if not (
            len(parts) >= 6 and "/".join(parts[:5]) == "search/api/v1-1/ibmcom/appid"
        ):
            return None
        app_id = parts[5] or app_id
    elif host in {"www.ibm.com", "ibm.com"}:
        if "/careers" not in path:
            return None
    elif host == "careers.ibm.com":
        pass
    else:
        return None

    config: dict[str, Any] = {
        "app_id": app_id,
        "scope": scope,
        "company": "IBM",
    }
    if query:
        config["keywords"] = query
    base_url = (
        f"https://www.ibm.com/careers/search?q={query}"
        if query
        else "https://www.ibm.com/careers/search"
    )
    suggested = _suggested_name(page_title, "IBM Careers")
    return SourceDetection(
        adapter_key="ibm_careers",
        suggested_name=suggested,
        base_url=base_url,
        default_config=config,
        query_url=base_url,
    )


def _first(params: dict[str, list[str]], *keys: str) -> str:
    for key in keys:
        values = params.get(key) or []
        if values and str(values[0]).strip():
            return str(values[0]).strip()
    return ""


def _suggested_name(page_title: str | None, fallback: str) -> str:
    if not page_title:
        return fallback
    cleaned = page_title.strip()
    for suffix in (" | IBM Careers", " - IBM Careers", " | IBM", " - IBM"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
    return cleaned or fallback
