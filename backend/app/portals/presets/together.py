"""Together AI curated portal preset."""

from __future__ import annotations

from app.portals.catalog_helpers import gh_preset

PORTAL = gh_preset(
    "togetherai",
    "Together AI",
    category="ai",
    portal_id="together",
)
