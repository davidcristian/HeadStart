"""MicroStrategy curated portal preset."""

from __future__ import annotations

from app.portals.catalog_helpers import sr_preset

PORTAL = sr_preset(
    "MicroStrategy1",
    "MicroStrategy",
    portal_id="microstrategy",
    category="big_tech",
)
