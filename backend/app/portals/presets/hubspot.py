"""HubSpot curated portal preset."""

from __future__ import annotations

from app.portals.catalog_helpers import PortalPreset

PORTAL = PortalPreset(
    id="hubspot",
    company_name="HubSpot",
    category="unicorn",
    adapter_key="greenhouse",
    base_url="https://boards.greenhouse.io/hubspotjobs",
    default_config={
        "board_token": "hubspotjobs",
        "company": "HubSpot",
        "portal_id": "hubspot",
    },
)
