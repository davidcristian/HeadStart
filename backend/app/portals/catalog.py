"""Static catalog of curated employer job portals.

Each preset maps to an existing scraper adapter with verified public API access.
Update this list when employers change ATS or board slugs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

PortalCategory = Literal["big_tech", "unicorn", "ai"]


@dataclass(frozen=True, slots=True)
class PortalPreset:
    """A pre-configured careers portal users can add in one click."""

    id: str
    company_name: str
    category: PortalCategory
    adapter_key: str
    base_url: str
    default_config: dict[str, Any]


def _gh(token: str, company: str) -> PortalPreset:
    return PortalPreset(
        id=token,
        company_name=company,
        category="unicorn",
        adapter_key="greenhouse",
        base_url=f"https://boards.greenhouse.io/{token}",
        default_config={"board_token": token, "company": company, "portal_id": token},
    )


def _lever(site: str, company: str, *, category: PortalCategory = "unicorn") -> PortalPreset:
    return PortalPreset(
        id=site,
        company_name=company,
        category=category,
        adapter_key="lever",
        base_url=f"https://jobs.lever.co/{site}",
        default_config={"site": site, "company": company, "portal_id": site},
    )


def _ashby(board: str, company: str, *, category: PortalCategory = "unicorn") -> PortalPreset:
    return PortalPreset(
        id=board,
        company_name=company,
        category=category,
        adapter_key="ashby",
        base_url=f"https://jobs.ashbyhq.com/{board}",
        default_config={"board": board, "company": company, "portal_id": board},
    )


def _workday(
    *,
    portal_id: str,
    company: str,
    tenant: str,
    site: str,
    region: str,
    locale: str = "en-US",
    category: PortalCategory = "big_tech",
) -> PortalPreset:
    base = f"https://{tenant}.{region}.myworkdayjobs.com/{locale}/{site}"
    return PortalPreset(
        id=portal_id,
        company_name=company,
        category=category,
        adapter_key="workday",
        base_url=base,
        default_config={
            "tenant": tenant,
            "site": site,
            "region": region,
            "locale": locale,
            "company": company,
            "portal_id": portal_id,
        },
    )


CURATED_PORTALS: tuple[PortalPreset, ...] = (
    # Big tech (Workday-backed career sites with public CXS APIs)
    _workday(
        portal_id="nvidia",
        company="NVIDIA",
        tenant="nvidia",
        site="NVIDIAExternalCareerSite",
        region="wd5",
    ),
    _workday(
        portal_id="salesforce",
        company="Salesforce",
        tenant="salesforce",
        site="External_Career_Site",
        region="wd12",
    ),
    _workday(
        portal_id="adobe",
        company="Adobe",
        tenant="adobe",
        site="external_experienced",
        region="wd5",
    ),
    # Unicorns & high-growth (Greenhouse)
    _gh("stripe", "Stripe"),
    PortalPreset(
        id="figma",
        company_name="Figma",
        category="unicorn",
        adapter_key="greenhouse",
        base_url="https://boards.greenhouse.io/figma",
        default_config={"board_token": "figma", "company": "Figma", "portal_id": "figma"},
    ),
    PortalPreset(
        id="airbnb",
        company_name="Airbnb",
        category="unicorn",
        adapter_key="greenhouse",
        base_url="https://boards.greenhouse.io/airbnb",
        default_config={"board_token": "airbnb", "company": "Airbnb", "portal_id": "airbnb"},
    ),
    PortalPreset(
        id="coinbase",
        company_name="Coinbase",
        category="unicorn",
        adapter_key="greenhouse",
        base_url="https://boards.greenhouse.io/coinbase",
        default_config={"board_token": "coinbase", "company": "Coinbase", "portal_id": "coinbase"},
    ),
    PortalPreset(
        id="discord",
        company_name="Discord",
        category="unicorn",
        adapter_key="greenhouse",
        base_url="https://boards.greenhouse.io/discord",
        default_config={"board_token": "discord", "company": "Discord", "portal_id": "discord"},
    ),
    PortalPreset(
        id="cloudflare",
        company_name="Cloudflare",
        category="unicorn",
        adapter_key="greenhouse",
        base_url="https://boards.greenhouse.io/cloudflare",
        default_config={
            "board_token": "cloudflare",
            "company": "Cloudflare",
            "portal_id": "cloudflare",
        },
    ),
    PortalPreset(
        id="datadog",
        company_name="Datadog",
        category="unicorn",
        adapter_key="greenhouse",
        base_url="https://boards.greenhouse.io/datadog",
        default_config={"board_token": "datadog", "company": "Datadog", "portal_id": "datadog"},
    ),
    PortalPreset(
        id="anduril",
        company_name="Anduril",
        category="unicorn",
        adapter_key="greenhouse",
        base_url="https://boards.greenhouse.io/andurilindustries",
        default_config={
            "board_token": "andurilindustries",
            "company": "Anduril",
            "portal_id": "anduril",
        },
    ),
    # Unicorns (Lever)
    _lever("netflix", "Netflix", category="big_tech"),
    _lever("spotify", "Spotify", category="big_tech"),
    _lever("plaid", "Plaid"),
    # Unicorns (Ashby)
    _ashby("notion", "Notion"),
    _ashby("ramp", "Ramp"),
    _ashby("linear", "Linear"),
    _ashby("deel", "Deel"),
    # AI leaders
    _ashby("openai", "OpenAI", category="ai"),
    PortalPreset(
        id="anthropic",
        company_name="Anthropic",
        category="ai",
        adapter_key="greenhouse",
        base_url="https://boards.greenhouse.io/anthropic",
        default_config={
            "board_token": "anthropic",
            "company": "Anthropic",
            "portal_id": "anthropic",
        },
    ),
    PortalPreset(
        id="databricks",
        company_name="Databricks",
        category="ai",
        adapter_key="greenhouse",
        base_url="https://boards.greenhouse.io/databricks",
        default_config={
            "board_token": "databricks",
            "company": "Databricks",
            "portal_id": "databricks",
        },
    ),
    PortalPreset(
        id="scaleai",
        company_name="Scale AI",
        category="ai",
        adapter_key="greenhouse",
        base_url="https://boards.greenhouse.io/scaleai",
        default_config={"board_token": "scaleai", "company": "Scale AI", "portal_id": "scaleai"},
    ),
)


def list_portal_presets(
    *,
    category: PortalCategory | None = None,
    query: str | None = None,
) -> list[PortalPreset]:
    """Return catalog entries filtered by category and/or company name search."""
    items = list(CURATED_PORTALS)
    if category is not None:
        items = [p for p in items if p.category == category]
    if query:
        needle = query.casefold().strip()
        if needle:
            items = [p for p in items if needle in p.company_name.casefold() or needle in p.id]
    return items
