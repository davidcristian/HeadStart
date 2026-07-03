"""Western Digital curated portal preset."""

from __future__ import annotations

from app.portals.catalog_helpers import sr_preset

PORTAL = sr_preset(
    "WesternDigital",
    "Western Digital",
    portal_id="westerndigital",
    category="big_tech",
)
