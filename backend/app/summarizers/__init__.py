"""Summarizers: pluggable "why this matches" blurb generators.

Public surface mirrors `app.scrapers` / `app.notifiers`: resolve an adapter by
key with `get_summarizer`, list keys with `available_summarizers`.
"""

from app.summarizers.base import (
    Summarizer,
    available_summarizers,
    get_summarizer,
    register_summarizer,
)
from app.summarizers.types import SummaryContext

__all__ = [
    "Summarizer",
    "SummaryContext",
    "available_summarizers",
    "get_summarizer",
    "register_summarizer",
]
