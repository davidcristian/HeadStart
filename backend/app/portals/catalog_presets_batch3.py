"""Phase 19 portal catalog batch — presets on existing adapters only."""

from __future__ import annotations

from app.portals.catalog_helpers import PortalPreset, gh_preset, workday_preset

BATCH3_PORTALS: tuple[PortalPreset, ...] = (
    workday_preset(
        portal_id="zoom",
        company="Zoom",
        tenant="zoom",
        site="Zoom",
        region="wd5",
    ),
    gh_preset("purestorage", "Pure Storage", category="big_tech"),
    gh_preset("unity3d", "Unity", category="big_tech"),
    gh_preset("gusto", "Gusto"),
    gh_preset("samsara", "Samsara"),
    gh_preset("roblox", "Roblox"),
    gh_preset("klaviyo", "Klaviyo"),
    gh_preset("riotgames", "Riot Games"),
    gh_preset("chime", "Chime"),
    gh_preset("checkr", "Checkr"),
    gh_preset("mercury", "Mercury"),
    gh_preset("fastly", "Fastly"),
    gh_preset("pagerduty", "PagerDuty"),
    gh_preset("squarespace", "Squarespace"),
    PortalPreset(
        id="hubspot",
        company_name="HubSpot",
        category="unicorn",
        adapter_key="greenhouse",
        base_url="https://boards.greenhouse.io/hubspotjobs",
        default_config={
            "board_token": "hubspotjobs",
            "company": "HubSpot",
            "portal_id": "hubspot",
        },
    ),
)
