"""Snyk curated portal preset (Workday External board)."""

from __future__ import annotations

from app.portals.catalog_helpers import PortalPreset
from app.portals.catalog_helpers_workday import workday_preset

PORTAL: PortalPreset = workday_preset(
    portal_id="snyk",
    company="Snyk",
    tenant="snyk",
    site="External",
    region="wd103",
    category="unicorn",
)
