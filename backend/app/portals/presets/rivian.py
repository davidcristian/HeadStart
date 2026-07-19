"""Rivian curated portal preset (iCIMS / Jibe Attract)."""

from __future__ import annotations

from app.portals.catalog_helpers import icims_preset

PORTAL = icims_preset(
    portal_id="rivian",
    company="Rivian",
    careers_base_url="https://careers.rivian.com",
    category="unicorn",
)
