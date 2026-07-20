"""Rippling curated portal preset (Rippling ATS)."""

from __future__ import annotations

from app.portals.catalog_helpers_rippling import rippling_preset

PORTAL = rippling_preset(
    portal_id="rippling",
    company="Rippling",
    board="rippling",
    category="unicorn",
)
