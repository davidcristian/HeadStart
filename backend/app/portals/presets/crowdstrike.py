"""CrowdStrike curated portal preset."""

from __future__ import annotations

from app.portals.catalog_helpers import PortalPreset, workday_preset

PORTAL: PortalPreset = workday_preset(
    portal_id="crowdstrike",
    company="CrowdStrike",
    tenant="crowdstrike",
    site="crowdstrikecareers",
    region="wd5",
)
