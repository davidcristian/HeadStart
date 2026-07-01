"""Applier base class and registry.

Adapters subclass `Applier`, implement `apply`, and self-register with
`@register_applier("key")`. The key matches a source's `adapter_key` when that
source supports auto-apply. Resolve by key via `get_applier`.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable

from app.appliers.types import ApplyContext, ApplyResult
from app.scrapers.http import HttpClient


class Applier(ABC):
    """Submit (or preview) a job application for a single posting."""

    def __init__(self, http: HttpClient | None = None) -> None:
        self.http = http or HttpClient()

    @abstractmethod
    def apply(self, ctx: ApplyContext) -> ApplyResult:
        """Submit or preview an application for the given job context."""
        raise NotImplementedError


_REGISTRY: dict[str, type[Applier]] = {}


def register_applier(key: str) -> Callable[[type[Applier]], type[Applier]]:
    """Class decorator that registers an adapter under `key`."""

    def decorator(cls: type[Applier]) -> type[Applier]:
        if key in _REGISTRY and _REGISTRY[key] is not cls:
            raise ValueError(f"Applier key '{key}' is already registered.")
        _REGISTRY[key] = cls
        return cls

    return decorator


def get_applier(key: str, http: HttpClient | None = None) -> Applier:
    """Instantiate the adapter registered under `key`."""
    from app.appliers import adapters  # noqa: F401

    try:
        cls = _REGISTRY[key]
    except KeyError as exc:
        raise KeyError(
            f"No applier registered for '{key}'. Available: {sorted(_REGISTRY)}"
        ) from exc
    return cls(http=http)


def available_appliers() -> list[str]:
    from app.appliers import adapters  # noqa: F401

    return sorted(_REGISTRY)


def has_applier(key: str) -> bool:
    from app.appliers import adapters  # noqa: F401

    return key in _REGISTRY
