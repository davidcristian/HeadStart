"""Freshworks curated portal preset (SmartRecruiters)."""

from __future__ import annotations

from app.portals.catalog_helpers import sr_preset

PORTAL = sr_preset(
    "Freshworks",
    "Freshworks",
    category="unicorn",
    portal_id="freshworks",
)
