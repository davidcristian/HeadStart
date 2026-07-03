"""Email classifier base class and registry."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from app.email_classifiers.types import EmailClassificationResult, EmailClassifyContext


class EmailClassifier(ABC):
    """Classify one inbound recruiter email."""

    @abstractmethod
    def classify(self, ctx: EmailClassifyContext) -> EmailClassificationResult:
        """Return a structured label; raise on unrecoverable failure."""
        raise NotImplementedError


_REGISTRY: dict[str, type[EmailClassifier]] = {}


def register_email_classifier(
    key: str,
) -> Callable[[type[EmailClassifier]], type[EmailClassifier]]:
    def decorator(cls: type[EmailClassifier]) -> type[EmailClassifier]:
        if key in _REGISTRY and _REGISTRY[key] is not cls:
            raise ValueError(f"Email classifier key '{key}' is already registered.")
        _REGISTRY[key] = cls
        return cls

    return decorator


def get_email_classifier(key: str, *, settings: Any | None = None) -> EmailClassifier:
    from app.email_classifiers import adapters  # noqa: F401

    try:
        cls = _REGISTRY[key]
    except KeyError as exc:
        raise KeyError(f"No email classifier for '{key}'. Available: {sorted(_REGISTRY)}") from exc
    if settings is None:
        return cls()
    return cls(settings=settings)  # type: ignore[call-arg]


def available_email_classifiers() -> list[str]:
    from app.email_classifiers import adapters  # noqa: F401

    return sorted(_REGISTRY)
