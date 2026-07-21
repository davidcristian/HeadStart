"""RTX curated portal preset (Phenom People careers site)."""

from __future__ import annotations

from app.portals.catalog_helpers_phenom import phenom_preset

PORTAL = phenom_preset(
    portal_id="rtx",
    company="RTX",
    careers_base_url="https://careers.rtx.com",
    country="global",
    locale="en_global",
    ref_num="RAYTGLOBAL",
    category="big_tech",
)
