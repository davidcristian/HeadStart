"""Summarizer base class and registry (strategy pattern).

A summarizer turns a job posting into a short "why this matches" blurb that the
pipeline attaches to notifications. Adapters subclass `Summarizer`, implement
`summarize`, and self-register with `@register_summarizer("key")`. Resolve by
key via `get_summarizer`.

This mirrors the scraper/notifier registries so adding an AI provider is a
one-file change, reached only through this interface.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from app.scrapers.types import JobPosting
from app.summarizers.types import SummaryContext


class Summarizer(ABC):
    """Produce a short match-explanation blurb per job posting."""

    @abstractmethod
    def summarize(self, ctx: SummaryContext, jobs: list[JobPosting]) -> list[str]:
        """Return one blurb per posting, aligned with and same length as `jobs`."""
        raise NotImplementedError


_REGISTRY: dict[str, type[Summarizer]] = {}


def register_summarizer(key: str) -> Callable[[type[Summarizer]], type[Summarizer]]:
    def decorator(cls: type[Summarizer]) -> type[Summarizer]:
        if key in _REGISTRY and _REGISTRY[key] is not cls:
            raise ValueError(f"Summarizer key '{key}' is already registered.")
        _REGISTRY[key] = cls
        return cls

    return decorator


def get_summarizer(key: str, *, settings: Any | None = None) -> Summarizer:
    from app.summarizers import adapters  # noqa: F401  (triggers registration)

    try:
        cls = _REGISTRY[key]
    except KeyError as exc:
        raise KeyError(
            f"No summarizer registered for '{key}'. Available: {sorted(_REGISTRY)}"
        ) from exc
    if settings is None:
        return cls()
    return cls(settings=settings)  # type: ignore[call-arg]


def available_summarizers() -> list[str]:
    from app.summarizers import adapters  # noqa: F401

    return sorted(_REGISTRY)
