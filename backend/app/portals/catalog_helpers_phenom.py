"""Phenom People portal preset factory."""

from __future__ import annotations

from typing import Any

from app.portals.catalog_helpers import PortalCategory, PortalPreset


def phenom_preset(
    *,
    portal_id: str,
    company: str,
    careers_base_url: str,
    country: str,
    locale: str,
    ref_num: str,
    keywords: str = "",
    category: PortalCategory = "unicorn",
) -> PortalPreset:
    """Build a preset for a Phenom People careers site with public ``/widgets`` search."""
    base = careers_base_url.rstrip("/")
    config: dict[str, Any] = {
        "company": company,
        "careers_base_url": base,
        "country": country,
        "locale": locale,
        "ref_num": ref_num,
        "portal_id": portal_id,
    }
    if keywords.strip():
        config["keywords"] = keywords.strip()
    return PortalPreset(
        id=portal_id,
        company_name=company,
        category=category,
        adapter_key="phenom",
        base_url=base,
        default_config=config,
    )
