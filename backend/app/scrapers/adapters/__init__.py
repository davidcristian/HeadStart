"""Importing this package registers all built-in scraper adapters.

Add a new adapter by creating a module here and importing it below. Nothing
else in the codebase needs to change (see docs/recipes.md).
"""

from app.scrapers.adapters import (
    amazon_jobs,
    apple_careers,
    ashby,
    generic_html,
    google_careers,
    greenhouse,
    ibm_careers,
    icims,
    indeed,
    lever,
    linkedin,
    meta_careers,
    microsoft_careers,
    phenom,
    playwright_html,
    rippling,
    shopify_careers,
    smartrecruiters,
    snowflake_careers,
    uber_careers,
    workday,
)

__all__ = [
    "amazon_jobs",
    "apple_careers",
    "ashby",
    "generic_html",
    "google_careers",
    "greenhouse",
    "ibm_careers",
    "icims",
    "indeed",
    "lever",
    "linkedin",
    "meta_careers",
    "microsoft_careers",
    "phenom",
    "playwright_html",
    "rippling",
    "shopify_careers",
    "smartrecruiters",
    "snowflake_careers",
    "uber_careers",
    "workday",
]
