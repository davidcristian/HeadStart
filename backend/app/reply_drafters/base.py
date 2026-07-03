"""Reply drafter base class and registry."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from app.reply_drafters.types import ReplyDraftContext, ReplyDraftResult


class ReplyDrafter(ABC):
    """Draft a recruiter follow-up reply for one classified inbound email."""

    @abstractmethod
    def draft(self, ctx: ReplyDraftContext) -> ReplyDraftResult:
        """Return a reply subject and body; raise on unrecoverable failure."""
        raise NotImplementedError


_REGISTRY: dict[str, type[ReplyDrafter]] = {}


def register_reply_drafter(key: str) -> Callable[[type[ReplyDrafter]], type[ReplyDrafter]]:
    def decorator(cls: type[ReplyDrafter]) -> type[ReplyDrafter]:
        if key in _REGISTRY and _REGISTRY[key] is not cls:
            raise ValueError(f"Reply drafter key '{key}' is already registered.")
        _REGISTRY[key] = cls
        return cls

    return decorator


def get_reply_drafter(key: str, *, settings: Any | None = None) -> ReplyDrafter:
    from app.reply_drafters import adapters  # noqa: F401

    try:
        cls = _REGISTRY[key]
    except KeyError as exc:
        raise KeyError(f"No reply drafter for '{key}'. Available: {sorted(_REGISTRY)}") from exc
    if settings is None:
        return cls()
    return cls(settings=settings)  # type: ignore[call-arg]


def available_reply_drafters() -> list[str]:
    from app.reply_drafters import adapters  # noqa: F401

    return sorted(_REGISTRY)
