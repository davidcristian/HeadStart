"""Summarizer base class and registry (strategy pattern).

A summarizer turns a job posting into a short "why this matches" blurb that the
pipeline attaches to notifications. Adapters subclass `Summarizer`, implement
`summarize`, and self-register with `@register_summarizer("key")`. Resolve by
key via `get_summarizer`.

This mirrors the scraper/notifier registries so adding an AI provider is a
one-file change, reached only through this interface.
"""

from abc import ABC, abstractmethod

from app.ai.registry import AdapterRegistry
from app.scrapers.types import JobPosting
from app.summarizers.types import SummaryContext


class Summarizer(ABC):
    """Produce a short match-explanation blurb per job posting."""

    @abstractmethod
    def summarize(self, ctx: SummaryContext, jobs: list[JobPosting]) -> list[str]:
        """Return one blurb per posting, aligned with and same length as `jobs`."""
        raise NotImplementedError


_registry: AdapterRegistry[Summarizer] = AdapterRegistry(
    noun="summarizer", adapters_module="app.summarizers.adapters"
)
register_summarizer = _registry.register
get_summarizer = _registry.get
available_summarizers = _registry.available
