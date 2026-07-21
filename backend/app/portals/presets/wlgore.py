"""W. L. Gore & Associates curated portal preset (SuccessFactors)."""

from __future__ import annotations

from app.portals.catalog_helpers_successfactors import successfactors_preset

PORTAL = successfactors_preset(
    portal_id="wlgore",
    company="W. L. Gore & Associates",
    careers_base_url="https://wlgore.jobs.hr.cloud.sap",
    category="unicorn",
)
