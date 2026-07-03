"""SmartRecruiters employer presets (Phase 17 catalog batch)."""

from __future__ import annotations

from app.portals.catalog_helpers import PortalPreset, sr_preset

SMARTRECRUITERS_PORTALS: tuple[PortalPreset, ...] = (
    sr_preset("Atlassian2", "Atlassian", portal_id="atlassian", category="big_tech"),
    sr_preset("BoschGroup", "Bosch", portal_id="bosch", category="big_tech"),
    sr_preset("ServiceNow", "ServiceNow", portal_id="servicenow", category="big_tech"),
    sr_preset("WesternDigital", "Western Digital", portal_id="westerndigital", category="big_tech"),
    sr_preset("Samsung1", "Samsung", portal_id="samsung", category="big_tech"),
    sr_preset("ASML1", "ASML", portal_id="asml", category="big_tech"),
    sr_preset("Ericsson16", "Ericsson", portal_id="ericsson", category="big_tech"),
    sr_preset("Infosys2", "Infosys", portal_id="infosys", category="big_tech"),
    sr_preset("DocuSign", "DocuSign", portal_id="docusign", category="big_tech"),
    sr_preset("MicroStrategy1", "MicroStrategy", portal_id="microstrategy", category="big_tech"),
    sr_preset("Endava", "Endava", portal_id="endava"),
    sr_preset("McDonaldsCorporation", "McDonald's", portal_id="mcdonalds"),
)
