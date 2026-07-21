"""Workable careers URL detection helpers."""

from __future__ import annotations

import re
from typing import Any

from app.scrapers.url_detect_types import SourceDetection

_ACCOUNT_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$")
_RESERVED_PATHS = frozenset({"api", "j", "jobs", "login", "oauth", "static", "assets"})


def detect_workable(parsed: Any, host: str, page_title: str | None) -> SourceDetection | None:
    """Return adapter defaults when the URL matches a Workable careers or widget API."""
    if host != "apply.workable.com":
        return None

    parts = [part for part in parsed.path.split("/") if part]
    account = ""
    if len(parts) >= 5 and "/".join(parts[:4]) == "api/v1/widget/accounts":
        if _ACCOUNT_RE.fullmatch(parts[4]):
            account = parts[4]
    elif parts and parts[0] not in _RESERVED_PATHS and _ACCOUNT_RE.fullmatch(parts[0]):
        account = parts[0]
    if not account:
        return None

    company = _humanize_slug(account)
    suggested_name = _suggested_name(page_title, company)
    base_url = f"https://apply.workable.com/{account}"
    return SourceDetection(
        adapter_key="workable",
        suggested_name=suggested_name,
        base_url=base_url,
        default_config={"account": account, "company": company},
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
