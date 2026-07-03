"""Zoom curated portal preset."""

from __future__ import annotations

from app.portals.catalog_helpers import PortalPreset, workday_preset

PORTAL: PortalPreset = workday_preset(
    portal_id="zoom",
    company="Zoom",
    tenant="zoom",
    site="Zoom",
    region="wd5",
)
