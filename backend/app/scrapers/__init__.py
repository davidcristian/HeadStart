"""Scraper subsystem: pluggable adapters that normalize job postings.

Public API:
    from app.scrapers import get_scraper, available_scrapers, register_scraper
"""

from app.scrapers.base import (
    Scraper,
    available_scrapers,
    get_scraper,
    register_scraper,
)
from app.scrapers.types import JobPosting, ScrapeContext

__all__ = [
    "JobPosting",
    "ScrapeContext",
    "Scraper",
    "available_scrapers",
    "get_scraper",
    "register_scraper",
]
