"""Rippling ATS URL detection helpers."""

from __future__ import annotations

import re
from typing import Any

from app.scrapers.url_detect_types import SourceDetection

_BOARD_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$")


def detect_rippling(parsed: Any, host: str, page_title: str | None) -> SourceDetection | None:
    """Return adapter defaults when the URL matches a Rippling ATS board or API."""
    board = ""
    if host == "ats.rippling.com":
        parts = [part for part in parsed.path.split("/") if part]
        if parts and _BOARD_RE.fullmatch(parts[0]):
            board = parts[0]
    elif host == "api.rippling.com":
        parts = [part for part in parsed.path.split("/") if part]
        if (
            len(parts) >= 6
            and "/".join(parts[:5]) == "platform/api/ats/v1/board"
            and _BOARD_RE.fullmatch(parts[5])
        ):
            board = parts[5]
    if not board:
        return None

    company = _humanize_slug(board)
    suggested_name = _suggested_name(page_title, company)
    base_url = f"https://ats.rippling.com/{board}"
    return SourceDetection(
        adapter_key="rippling",
        suggested_name=suggested_name,
        base_url=base_url,
        default_config={"board": board, "company": company},
        query_url=base_url,
    )


def _humanize_slug(slug: str) -> str:
    cleaned = slug.replace("-", " ").replace("_", " ").strip()
    return cleaned.title() if cleaned else slug


def _suggested_name(page_title: str | None, fallback: str) -> str:
    if not page_title:
        return fallback
    cleaned = page_title.strip()
    for suffix in (" Careers", " Jobs", " Job Board", " | Careers", " - Careers"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
    return cleaned or fallback
