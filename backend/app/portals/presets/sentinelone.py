"""SentinelOne curated portal preset."""

from __future__ import annotations

from app.portals.catalog_helpers import PortalPreset

PORTAL = PortalPreset(
    id="sentinelone",
    company_name="SentinelOne",
    category="unicorn",
    adapter_key="greenhouse",
    base_url="https://boards.greenhouse.io/sentinellabs",
    default_config={
        "board_token": "sentinellabs",
        "company": "SentinelOne",
        "portal_id": "sentinelone",
    },
)
