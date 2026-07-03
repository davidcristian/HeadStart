"""ServiceNow curated portal preset."""

from __future__ import annotations

from app.portals.catalog_helpers import sr_preset

PORTAL = sr_preset("ServiceNow", "ServiceNow", portal_id="servicenow", category="big_tech")
