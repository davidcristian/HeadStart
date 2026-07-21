"""CVS Health curated portal preset (Phenom People careers site)."""

from __future__ import annotations

from app.portals.catalog_helpers_phenom import phenom_preset

PORTAL = phenom_preset(
    portal_id="cvshealth",
    company="CVS Health",
    careers_base_url="https://jobs.cvshealth.com",
    country="us",
    locale="en_us",
    ref_num="CVSCHLUS",
    category="big_tech",
)
