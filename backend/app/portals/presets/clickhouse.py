"""ClickHouse curated portal preset."""

from __future__ import annotations

from app.portals.catalog_helpers import gh_preset

PORTAL = gh_preset("clickhouse", "ClickHouse", category="unicorn")
