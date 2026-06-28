"""Scraper base class and registry.

Adapters subclass `Scraper`, implement `fetch`, and self-register with
`@register_scraper("key")`. The rest of the system resolves them by key via
`get_scraper` and never imports a concrete adapter directly.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable

from app.scrapers.http import HttpClient
from app.scrapers.rate_limit import RateLimiter
from app.scrapers.types import JobPosting, ScrapeContext


class Scraper(ABC):
    """Fetch and normalize job postings from a single source."""

    def __init__(
        self,
        http: HttpClient | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._rate_limiter = rate_limiter
        self.http = http or HttpClient(rate_limiter=rate_limiter)

    @abstractmethod
    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        """Return the current postings for the given search context."""
        raise NotImplementedError


_REGISTRY: dict[str, type[Scraper]] = {}


def register_scraper(key: str) -> Callable[[type[Scraper]], type[Scraper]]:
    """Class decorator that registers an adapter under `key`."""

    def decorator(cls: type[Scraper]) -> type[Scraper]:
        if key in _REGISTRY and _REGISTRY[key] is not cls:
            raise ValueError(f"Scraper key '{key}' is already registered.")
        _REGISTRY[key] = cls
        return cls

    return decorator


def get_scraper(
    key: str,
    http: HttpClient | None = None,
    rate_limiter: RateLimiter | None = None,
) -> Scraper:
    """Instantiate the adapter registered under `key`."""
    # Importing the adapters package triggers registration of all built-ins.
    from app.scrapers import adapters  # noqa: F401

    try:
        cls = _REGISTRY[key]
    except KeyError as exc:
        raise KeyError(
            f"No scraper registered for '{key}'. Available: {sorted(_REGISTRY)}"
        ) from exc
    return cls(http=http, rate_limiter=rate_limiter)


def available_scrapers() -> list[str]:
    from app.scrapers import adapters  # noqa: F401

    return sorted(_REGISTRY)
