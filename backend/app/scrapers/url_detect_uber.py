"""Uber Careers URL detection helpers."""

from __future__ import annotations

import re
from typing import Any

from app.scrapers.url_detect_types import SourceDetection

_HOST_RE = re.compile(r"^(?:www\.)?uber\.com$", re.IGNORECASE)
_CAREERS_PATH_RE = re.compile(r"^/(?:[a-z]{2}/[a-z]{2}/)?careers(?:/|$)", re.IGNORECASE)
_JOB_DETAIL_RE = re.compile(r"/careers/list/\d+/?$", re.IGNORECASE)


def detect_uber_careers(parsed: Any, host: str, page_title: str | None) -> SourceDetection | None:
    """Return adapter defaults when the URL matches Uber Careers."""
    if not _HOST_RE.match(host):
        return None
    if not _CAREERS_PATH_RE.match(parsed.path):
        return None
    if _JOB_DETAIL_RE.search(parsed.path):
        return None

    careers_locale_path = _careers_locale_path(parsed.path)
    base_url = f"https://www.uber.com/{careers_locale_path}/careers/list/"
    return SourceDetection(
        adapter_key="uber_careers",
        suggested_name=_uber_suggested_name(page_title),
        base_url=base_url,
        default_config={
            "company": "Uber",
            "portal_id": "uber",
            "careers_locale_path": careers_locale_path,
        },
        query_url=base_url,
    )


def _careers_locale_path(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    if len(parts) >= 2 and len(parts[0]) == 2 and len(parts[1]) == 2:
        return f"{parts[0]}/{parts[1]}"
    return "us/en"


def _uber_suggested_name(page_title: str | None) -> str:
    if page_title:
        cleaned = page_title.strip()
        for suffix in (
            " | Uber Careers",
            " - Uber Careers",
            " | Uber",
            " Careers",
        ):
            if cleaned.endswith(suffix):
                cleaned = cleaned[: -len(suffix)].strip()
        if cleaned:
            return cleaned
    return "Uber Careers"
