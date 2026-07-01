"""Curated job-portal presets for one-click source setup."""

from app.portals.catalog import (
    CURATED_PORTALS,
    PortalPreset,
    get_portal_preset,
    list_portal_presets,
)

__all__ = ["CURATED_PORTALS", "PortalPreset", "get_portal_preset", "list_portal_presets"]
