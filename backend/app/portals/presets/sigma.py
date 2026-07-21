"""Sigma curated portal preset."""

from __future__ import annotations

from app.portals.catalog_helpers import gh_preset

PORTAL = gh_preset(
    "sigmacomputing",
    "Sigma",
    category="unicorn",
    portal_id="sigma",
)
