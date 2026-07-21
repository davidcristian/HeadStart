"""Grafana Labs curated portal preset."""

from __future__ import annotations

from app.portals.catalog_helpers import gh_preset

PORTAL = gh_preset(
    "grafanalabs",
    "Grafana Labs",
    category="unicorn",
    portal_id="grafana",
)
