"""Splunk curated portal preset (Cisco Phenom careers site)."""

from __future__ import annotations

from app.portals.catalog_helpers_phenom import phenom_preset

PORTAL = phenom_preset(
    portal_id="splunk",
    company="Splunk",
    careers_base_url="https://careers.cisco.com",
    country="global",
    locale="en_global",
    ref_num="CISCISGLOBAL",
    keywords="Splunk",
    category="big_tech",
)
