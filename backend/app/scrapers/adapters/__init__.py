"""Importing this package registers all built-in scraper adapters.

Add a new adapter by creating a module here and importing it below. Nothing
else in the codebase needs to change (see docs/recipes.md).
"""

from app.scrapers.adapters import (
    ashby,
    generic_html,
    google_careers,
    greenhouse,
    indeed,
    lever,
    linkedin,
    microsoft_careers,
    playwright_html,
    workday,
)

__all__ = [
    "ashby",
    "generic_html",
    "google_careers",
    "greenhouse",
    "indeed",
    "lever",
    "linkedin",
    "microsoft_careers",
    "playwright_html",
    "workday",
]
