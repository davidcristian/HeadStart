"""Zillow curated portal preset."""

from __future__ import annotations

from app.portals.catalog_helpers import PortalPreset, workday_preset

PORTAL: PortalPreset = workday_preset(
    portal_id="zillow",
    company="Zillow",
    tenant="zillow",
    site="Zillow_Group_External",
    region="wd5",
)
