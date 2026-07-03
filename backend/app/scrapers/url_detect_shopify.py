"""Shopify Careers URL detection helpers."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs

from app.scrapers.url_detect_types import SourceDetection

_HOST_RE = re.compile(r"^(?:www\.)?shopify\.com$", re.IGNORECASE)


def detect_shopify_careers(
    parsed: Any, host: str, page_title: str | None
) -> SourceDetection | None:
    """Return adapter defaults when the URL matches Shopify Careers."""
    if not _HOST_RE.match(host):
        return None
    if not parsed.path.rstrip("/").startswith("/careers"):
        return None
    if "_f" in parsed.path and re.search(
        r"/careers/[^/]+_[0-9a-f-]{36}$", parsed.path, re.IGNORECASE
    ):
        return None

    base_url = "https://www.shopify.com/careers"
    params = parse_qs(parsed.query, keep_blank_values=True)
    config: dict[str, Any] = {"company": "Shopify", "portal_id": "shopify"}
    keyword = (params.get("q") or params.get("search") or [""])[0].strip()
    if keyword:
        config["q"] = keyword

    return SourceDetection(
        adapter_key="shopify_careers",
        suggested_name=_shopify_suggested_name(keyword, page_title),
        base_url=base_url,
        default_config=config,
        query_url=parsed.geturl() if parsed.path.rstrip("/") == "/careers" else base_url,
    )


def _shopify_suggested_name(keyword: str, page_title: str | None) -> str:
    if page_title:
        cleaned = page_title.strip()
        for suffix in (
            " - Shopify",
            " | Shopify Careers",
            " | Shopify",
            " Careers",
        ):
            if cleaned.endswith(suffix):
                cleaned = cleaned[: -len(suffix)].strip()
        if cleaned:
            return cleaned
    return "Shopify / " + keyword if keyword else "Shopify Careers"
