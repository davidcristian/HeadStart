"""Cover letter generator base class and registry."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from app.cover_letters.types import CoverLetterContext


class CoverLetterGenerator(ABC):
    """Produce a cover letter for one job application."""

    @abstractmethod
    def generate(self, ctx: CoverLetterContext) -> str:
        """Return cover letter text; raise on unrecoverable failure."""
        raise NotImplementedError


_REGISTRY: dict[str, type[CoverLetterGenerator]] = {}


def register_cover_letter_generator(
    key: str,
) -> Callable[[type[CoverLetterGenerator]], type[CoverLetterGenerator]]:
    def decorator(cls: type[CoverLetterGenerator]) -> type[CoverLetterGenerator]:
        if key in _REGISTRY and _REGISTRY[key] is not cls:
            raise ValueError(f"Cover letter generator key '{key}' is already registered.")
        _REGISTRY[key] = cls
        return cls

    return decorator


def get_cover_letter_generator(key: str, *, settings: Any | None = None) -> CoverLetterGenerator:
    from app.cover_letters import adapters  # noqa: F401

    try:
        cls = _REGISTRY[key]
    except KeyError as exc:
        raise KeyError(
            f"No cover letter generator for '{key}'. Available: {sorted(_REGISTRY)}"
        ) from exc
    if settings is None:
        return cls()
    return cls(settings=settings)  # type: ignore[call-arg]


def available_cover_letter_generators() -> list[str]:
    from app.cover_letters import adapters  # noqa: F401

    return sorted(_REGISTRY)
