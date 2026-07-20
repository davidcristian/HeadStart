"""IBM Careers portal preset factory."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from app.portals.catalog_helpers import PortalCategory, PortalPreset


def ibm_careers_preset(
    *,
    portal_id: str,
    company: str,
    keywords: str,
    category: PortalCategory = "unicorn",
    app_id: str = "careers",
    scope: str = "careers2",
) -> PortalPreset:
    """Build a preset that searches IBM Careers with a Falcon keyword query."""
    query = keywords.strip()
    base = (
        f"https://www.ibm.com/careers/search?q={quote(query)}"
        if query
        else "https://www.ibm.com/careers/search"
    )
    config: dict[str, Any] = {
        "company": company,
        "app_id": app_id,
        "scope": scope,
        "portal_id": portal_id,
    }
    if query:
        config["keywords"] = query
    return PortalPreset(
        id=portal_id,
        company_name=company,
        category=category,
        adapter_key="ibm_careers",
        base_url=base,
        default_config=config,
    )
