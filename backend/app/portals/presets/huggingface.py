"""Hugging Face curated portal preset (Workable)."""

from __future__ import annotations

from app.portals.catalog_helpers_workable import workable_preset

PORTAL = workable_preset(
    portal_id="huggingface",
    company="Hugging Face",
    account="huggingface",
    category="ai",
)
