"""Rippling ATS portal preset factory."""

from __future__ import annotations

from app.portals.catalog_helpers import PortalCategory, PortalPreset


def rippling_preset(
    *,
    portal_id: str,
    company: str,
    board: str,
    category: PortalCategory = "unicorn",
) -> PortalPreset:
    """Build a preset for a Rippling ATS public board API slug."""
    base = f"https://ats.rippling.com/{board}"
    return PortalPreset(
        id=portal_id,
        company_name=company,
        category=category,
        adapter_key="rippling",
        base_url=base,
        default_config={
            "company": company,
            "board": board,
            "portal_id": portal_id,
        },
    )
