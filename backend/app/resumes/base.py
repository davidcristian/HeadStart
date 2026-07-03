"""Resume curator base class and registry."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from app.resumes.types import CuratedResumeFields, ResumeCurationContext


class ResumeCurator(ABC):
    """Tailor resume placeholder values for one job application."""

    @abstractmethod
    def curate(self, ctx: ResumeCurationContext) -> CuratedResumeFields:
        """Return curated placeholder values; raise on unrecoverable failure."""
        raise NotImplementedError


_REGISTRY: dict[str, type[ResumeCurator]] = {}


def register_resume_curator(key: str) -> Callable[[type[ResumeCurator]], type[ResumeCurator]]:
    def decorator(cls: type[ResumeCurator]) -> type[ResumeCurator]:
        if key in _REGISTRY and _REGISTRY[key] is not cls:
            raise ValueError(f"Resume curator key '{key}' is already registered.")
        _REGISTRY[key] = cls
        return cls

    return decorator


def get_resume_curator(key: str, *, settings: Any | None = None) -> ResumeCurator:
    from app.resumes import adapters  # noqa: F401

    try:
        cls = _REGISTRY[key]
    except KeyError as exc:
        raise KeyError(f"No resume curator for '{key}'. Available: {sorted(_REGISTRY)}") from exc
    if settings is None:
        return cls()
    return cls(settings=settings)  # type: ignore[call-arg]


def available_resume_curators() -> list[str]:
    from app.resumes import adapters  # noqa: F401

    return sorted(_REGISTRY)
