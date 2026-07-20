"""Grammarly curated portal preset (Ashby board hosted as Superhuman Platform Inc)."""

from __future__ import annotations

from app.portals.catalog_helpers import ashby_preset

# Grammarly careers redirect to Superhuman; openings live on the combined Ashby board.
PORTAL = ashby_preset(
    "Superhuman Platform Inc",
    "Grammarly",
    category="unicorn",
    portal_id="grammarly",
)
