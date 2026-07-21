"""GE HealthCare curated portal preset (Phenom People careers site)."""

from __future__ import annotations

from app.portals.catalog_helpers_phenom import phenom_preset

PORTAL = phenom_preset(
    portal_id="gehealthcare",
    company="GE HealthCare",
    careers_base_url="https://careers.gehealthcare.com",
    country="global",
    locale="en_global",
    ref_num="GEVGHLGLOBAL",
    category="big_tech",
)
