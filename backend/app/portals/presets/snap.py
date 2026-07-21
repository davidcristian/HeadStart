"""Snap Inc. curated portal preset (Workday myworkdaysite.com board)."""

from __future__ import annotations

from app.portals.catalog_helpers import PortalPreset
from app.portals.catalog_helpers_workday import workday_preset

PORTAL: PortalPreset = workday_preset(
    portal_id="snap",
    company="Snap",
    tenant="snapchat",
    site="snap",
    region="wd1",
    host_kind="site",
    category="big_tech",
)
