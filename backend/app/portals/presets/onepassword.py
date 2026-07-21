"""1Password curated portal preset."""

from __future__ import annotations

from app.portals.catalog_helpers import ashby_preset

PORTAL = ashby_preset(
    "1password",
    "1Password",
    category="unicorn",
    portal_id="onepassword",
)
