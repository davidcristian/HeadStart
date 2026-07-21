"""Workday portal preset factory (classic jobs host + myworkdaysite.com)."""

from __future__ import annotations

from app.portals.catalog_helpers import PortalCategory, PortalPreset


def workday_preset(
    *,
    portal_id: str,
    company: str,
    tenant: str,
    site: str,
    region: str,
    locale: str = "en-US",
    category: PortalCategory = "big_tech",
    host_kind: str = "jobs",
) -> PortalPreset:
    """Build a Workday CXS preset for ``*.myworkdayjobs.com`` or ``*.myworkdaysite.com``."""
    kind = host_kind.strip().lower()
    if kind in {"site", "myworkdaysite", "site.com"}:
        base = f"https://{region}.myworkdaysite.com/recruiting/{tenant}/{site}"
        kind = "site"
    else:
        base = f"https://{tenant}.{region}.myworkdayjobs.com/{locale}/{site}"
        kind = "jobs"
    return PortalPreset(
        id=portal_id,
        company_name=company,
        category=category,
        adapter_key="workday",
        base_url=base,
        default_config={
            "tenant": tenant,
            "site": site,
            "region": region,
            "locale": locale,
            "company": company,
            "portal_id": portal_id,
            "host_kind": kind,
        },
    )
