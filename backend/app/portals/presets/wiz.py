"""Wiz curated portal preset."""

from __future__ import annotations

from app.portals.catalog_helpers import PortalPreset

PORTAL = PortalPreset(
    id="wiz",
    company_name="Wiz",
    category="unicorn",
    adapter_key="greenhouse",
    base_url="https://boards.greenhouse.io/wizinc",
    default_config={
        "board_token": "wizinc",
        "company": "Wiz",
        "portal_id": "wiz",
    },
)
