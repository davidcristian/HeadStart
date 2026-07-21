"""Character.AI curated portal preset."""

from __future__ import annotations

from app.portals.catalog_helpers import ashby_preset

PORTAL = ashby_preset(
    "character",
    "Character.AI",
    category="ai",
    portal_id="characterai",
)
