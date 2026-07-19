"""Palo Alto Networks curated portal preset."""

from __future__ import annotations

from app.portals.catalog_helpers import PortalPreset, workday_preset

PORTAL: PortalPreset = workday_preset(
    portal_id="paloaltonetworks",
    company="Palo Alto Networks",
    tenant="paloaltonetworks",
    site="panwexternalcareers",
    region="wd5",
)
