"""SuccessFactors portal preset factory."""

from __future__ import annotations

from app.portals.catalog_helpers import PortalCategory, PortalPreset


def successfactors_preset(
    *,
    portal_id: str,
    company: str,
    careers_base_url: str,
    category: PortalCategory = "unicorn",
    locale: str = "en_US",
    category_id: int | None = None,
) -> PortalPreset:
    """Build a preset for a SuccessFactors Career Site Builder public board."""
    base = careers_base_url.rstrip("/")
    config: dict[str, str | int] = {
        "company": company,
        "careers_base_url": base,
        "locale": locale,
        "portal_id": portal_id,
    }
    if category_id is not None:
        config["category_id"] = category_id
    return PortalPreset(
        id=portal_id,
        company_name=company,
        category=category,
        adapter_key="successfactors",
        base_url=base,
        default_config=config,
    )
