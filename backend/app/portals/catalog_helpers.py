"""Portal preset types and factory helpers."""

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


def gh_preset(token: str, company: str, *, category: PortalCategory = "unicorn") -> PortalPreset:
    return PortalPreset(
        id=token,
        company_name=company,
        category=category,
        adapter_key="greenhouse",
        base_url=f"https://boards.greenhouse.io/{token}",
        default_config={"board_token": token, "company": company, "portal_id": token},
    )


def lever_preset(site: str, company: str, *, category: PortalCategory = "unicorn") -> PortalPreset:
    return PortalPreset(
        id=site,
        company_name=company,
        category=category,
        adapter_key="lever",
        base_url=f"https://jobs.lever.co/{site}",
        default_config={"site": site, "company": company, "portal_id": site},
    )


def ashby_preset(board: str, company: str, *, category: PortalCategory = "unicorn") -> PortalPreset:
    return PortalPreset(
        id=board,
        company_name=company,
        category=category,
        adapter_key="ashby",
        base_url=f"https://jobs.ashbyhq.com/{board}",
        default_config={"board": board, "company": company, "portal_id": board},
    )


def sr_preset(
    company_id: str,
    company: str,
    *,
    category: PortalCategory = "unicorn",
    portal_id: str | None = None,
) -> PortalPreset:
    """Build a SmartRecruiters preset; portal_id defaults to company_id when omitted."""
    pid = portal_id or company_id
    return PortalPreset(
        id=pid,
        company_name=company,
        category=category,
        adapter_key="smartrecruiters",
        base_url=f"https://careers.smartrecruiters.com/{company_id}",
        default_config={"company_id": company_id, "company": company, "portal_id": pid},
    )


def workday_preset(
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


def apple_careers_preset(
    *,
    portal_id: str = "apple",
    company: str = "Apple",
    locale: str = "en-us",
    category: PortalCategory = "big_tech",
) -> PortalPreset:
    base = f"https://jobs.apple.com/{locale}/search"
    return PortalPreset(
        id=portal_id,
        company_name=company,
        category=category,
        adapter_key="apple_careers",
        base_url=base,
        default_config={"company": company, "portal_id": portal_id, "locale": locale},
    )


def amazon_jobs_preset(
    *,
    portal_id: str = "amazon",
    company: str = "Amazon",
    locale: str = "en",
    category: PortalCategory = "big_tech",
) -> PortalPreset:
    base = f"https://www.amazon.jobs/{locale}/search"
    return PortalPreset(
        id=portal_id,
        company_name=company,
        category=category,
        adapter_key="amazon_jobs",
        base_url=base,
        default_config={"company": company, "portal_id": portal_id, "locale": locale},
    )


def google_careers_preset(
    *,
    portal_id: str = "google",
    company: str = "Google",
    category: PortalCategory = "big_tech",
) -> PortalPreset:
    base = "https://www.google.com/about/careers/applications/jobs/results/"
    return PortalPreset(
        id=portal_id,
        company_name=company,
        category=category,
        adapter_key="google_careers",
        base_url=base,
        default_config={"company": company, "portal_id": portal_id},
    )


def meta_careers_preset(
    *,
    portal_id: str = "meta",
    company: str = "Meta",
    category: PortalCategory = "big_tech",
) -> PortalPreset:
    base = "https://www.metacareers.com/jobsearch/"
    return PortalPreset(
        id=portal_id,
        company_name=company,
        category=category,
        adapter_key="meta_careers",
        base_url=base,
        default_config={"company": company, "portal_id": portal_id},
    )


def shopify_careers_preset(
    *,
    portal_id: str = "shopify",
    company: str = "Shopify",
    category: PortalCategory = "unicorn",
) -> PortalPreset:
    base = "https://www.shopify.com/careers"
    return PortalPreset(
        id=portal_id,
        company_name=company,
        category=category,
        adapter_key="shopify_careers",
        base_url=base,
        default_config={"company": company, "portal_id": portal_id},
    )


def uber_careers_preset(
    *,
    portal_id: str = "uber",
    company: str = "Uber",
    category: PortalCategory = "big_tech",
) -> PortalPreset:
    base = "https://www.uber.com/us/en/careers/list/"
    return PortalPreset(
        id=portal_id,
        company_name=company,
        category=category,
        adapter_key="uber_careers",
        base_url=base,
        default_config={
            "company": company,
            "portal_id": portal_id,
            "careers_locale_path": "us/en",
        },
    )


def snowflake_careers_preset(
    *,
    portal_id: str = "snowflake",
    company: str = "Snowflake",
    category: PortalCategory = "big_tech",
) -> PortalPreset:
    base = "https://careers.snowflake.com/us/en/search-results"
    return PortalPreset(
        id=portal_id,
        company_name=company,
        category=category,
        adapter_key="snowflake_careers",
        base_url=base,
        default_config={
            "company": company,
            "portal_id": portal_id,
            "board": "snowflake",
        },
    )


def microsoft_careers_preset(
    *,
    portal_id: str = "microsoft",
    company: str = "Microsoft",
    domain: str = "microsoft.com",
    category: PortalCategory = "big_tech",
) -> PortalPreset:
    base = "https://apply.careers.microsoft.com/careers"
    return PortalPreset(
        id=portal_id,
        company_name=company,
        category=category,
        adapter_key="microsoft_careers",
        base_url=base,
        default_config={
            "company": company,
            "domain": domain,
            "portal_id": portal_id,
        },
    )
