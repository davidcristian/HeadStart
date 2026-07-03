"""SmartRecruiters URL detection helpers."""

from __future__ import annotations

from typing import Any

from app.scrapers.url_detect_types import SourceDetection


def detect_smartrecruiters(
    parsed: Any, host: str, page_title: str | None
) -> SourceDetection | None:
    """Return adapter defaults when the URL matches a SmartRecruiters careers board."""
    company_id = ""
    if host in {"careers.smartrecruiters.com", "jobs.smartrecruiters.com"}:
        parts = [part for part in parsed.path.split("/") if part]
        company_id = parts[0] if parts else ""
    elif host == "api.smartrecruiters.com":
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 4 and parts[0] == "v1" and parts[1] == "companies":
            company_id = parts[2]
    if not company_id:
        return None

    company = _humanize_slug(company_id)
    suggested_name = _suggested_name(page_title, company)
    base_url = f"https://careers.smartrecruiters.com/{company_id}"
    return SourceDetection(
        adapter_key="smartrecruiters",
        suggested_name=suggested_name,
        base_url=base_url,
        default_config={"company_id": company_id, "company": company},
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
