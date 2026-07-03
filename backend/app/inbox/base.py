"""Mailbox connector base class and registry (strategy pattern).

Adapters subclass `MailboxConnector`, implement fetch/send/test, and self-register
with `@register_mailbox("key")`. Resolve by key via `get_mailbox`.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable

from app.inbox.types import (
    ConnectionTestResult,
    FetchResult,
    MailboxContext,
    OutboundMessage,
    SendResult,
)


class MailboxConnector(ABC):
    """Read and send mail for a configured mailbox."""

    @abstractmethod
    def fetch_messages(
        self,
        ctx: MailboxContext,
        *,
        since_uid: int | None = None,
        limit: int = 50,
    ) -> FetchResult:
        """Return up to `limit` messages, optionally after `since_uid`."""
        raise NotImplementedError

    @abstractmethod
    def send_message(self, ctx: MailboxContext, message: OutboundMessage) -> SendResult:
        """Send one plain-text message."""
        raise NotImplementedError

    @abstractmethod
    def test_connection(self, ctx: MailboxContext) -> ConnectionTestResult:
        """Verify IMAP and SMTP login without fetching mail."""
        raise NotImplementedError


_REGISTRY: dict[str, type[MailboxConnector]] = {}


def register_mailbox(key: str) -> Callable[[type[MailboxConnector]], type[MailboxConnector]]:
    """Class decorator that registers a connector under `key`."""

    def decorator(cls: type[MailboxConnector]) -> type[MailboxConnector]:
        if key in _REGISTRY and _REGISTRY[key] is not cls:
            raise ValueError(f"Mailbox connector key '{key}' is already registered.")
        _REGISTRY[key] = cls
        return cls

    return decorator


def get_mailbox(key: str) -> MailboxConnector:
    """Instantiate the connector registered under `key`."""
    from app.inbox import adapters  # noqa: F401

    try:
        cls = _REGISTRY[key]
    except KeyError as exc:
        raise KeyError(
            f"No mailbox connector registered for '{key}'. Available: {sorted(_REGISTRY)}"
        ) from exc
    return cls()


def available_mailboxes() -> list[str]:
    from app.inbox import adapters  # noqa: F401

    return sorted(_REGISTRY)
