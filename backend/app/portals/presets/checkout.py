"""Checkout.com curated portal preset."""

from __future__ import annotations

from app.portals.catalog_helpers import ashby_preset

PORTAL = ashby_preset(
    "checkout.com",
    "Checkout.com",
    category="unicorn",
    portal_id="checkout",
)
