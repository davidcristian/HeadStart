"""Notifier base class and registry (strategy pattern).

Adapters subclass `Notifier`, implement `send`, and self-register with
`@register_notifier("key")`. Resolve by key via `get_notifier`.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable

from app.notifiers.types import DeliveryResult, NotifyContext
from app.scrapers.types import JobPosting


class Notifier(ABC):
    """Deliver new job postings to a single channel."""

    @abstractmethod
    def send(self, ctx: NotifyContext, jobs: list[JobPosting]) -> list[DeliveryResult]:
        """Deliver each posting. Returns a per-posting result for logging."""
        raise NotImplementedError


_REGISTRY: dict[str, type[Notifier]] = {}


def register_notifier(key: str) -> Callable[[type[Notifier]], type[Notifier]]:
    def decorator(cls: type[Notifier]) -> type[Notifier]:
        if key in _REGISTRY and _REGISTRY[key] is not cls:
            raise ValueError(f"Notifier key '{key}' is already registered.")
        _REGISTRY[key] = cls
        return cls

    return decorator


def get_notifier(key: str) -> Notifier:
    from app.notifiers import adapters  # noqa: F401  (triggers registration)

    try:
        cls = _REGISTRY[key]
    except KeyError as exc:
        raise KeyError(
            f"No notifier registered for '{key}'. Available: {sorted(_REGISTRY)}"
        ) from exc
    return cls()


def available_notifiers() -> list[str]:
    from app.notifiers import adapters  # noqa: F401

    return sorted(_REGISTRY)
