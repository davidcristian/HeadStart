"""Red Hat curated portal preset (IBM Careers keyword search)."""

from __future__ import annotations

from app.portals.catalog_helpers_ibm import ibm_careers_preset

PORTAL = ibm_careers_preset(
    portal_id="redhat",
    company="Red Hat",
    keywords="Red Hat",
    category="big_tech",
)
