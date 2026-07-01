"""Static catalog of curated employer job portals.

Each preset maps to an existing scraper adapter with verified public API access.
Update catalog_presets.py when employers change ATS or board slugs.
"""

from __future__ import annotations

from app.portals.catalog_helpers import PortalCategory, PortalPreset
from app.portals.catalog_presets import CURATED_PORTALS

__all__ = [
    "CURATED_PORTALS",
    "PortalCategory",
    "PortalPreset",
    "get_portal_preset",
    "list_portal_presets",
]


def list_portal_presets(
    *,
    category: PortalCategory | None = None,
    query: str | None = None,
) -> list[PortalPreset]:
    """Return catalog entries filtered by category and/or company name search."""
    items = list(CURATED_PORTALS)
    if category is not None:
        items = [p for p in items if p.category == category]
    if query:
        needle = query.casefold().strip()
        if needle:
            items = [p for p in items if needle in p.company_name.casefold() or needle in p.id]
    return items


def get_portal_preset(portal_id: str) -> PortalPreset | None:
    """Look up a curated portal by its stable id."""
    for preset in CURATED_PORTALS:
        if preset.id == portal_id:
            return preset
    return None
