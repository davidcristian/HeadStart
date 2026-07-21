"""Workable portal preset factory."""

from __future__ import annotations

from app.portals.catalog_helpers import PortalCategory, PortalPreset


def workable_preset(
    *,
    portal_id: str,
    company: str,
    account: str,
    category: PortalCategory = "unicorn",
) -> PortalPreset:
    """Build a preset for a Workable public widget account slug."""
    base = f"https://apply.workable.com/{account}"
    return PortalPreset(
        id=portal_id,
        company_name=company,
        category=category,
        adapter_key="workable",
        base_url=base,
        default_config={
            "company": company,
            "account": account,
            "portal_id": portal_id,
        },
    )
