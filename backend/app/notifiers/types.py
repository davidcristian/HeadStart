"""Shared notifier data types."""

from typing import Any

from pydantic import BaseModel, Field


class NotifyContext(BaseModel):
    """Everything a notifier needs to deliver to one target."""

    target_type: str
    config: dict[str, Any] = Field(default_factory=dict)
    digest: bool = False
    search_name: str | None = None
    # Preferred locale for user-facing copy; None → DEFAULT_LOCALE.
    locale: str | None = None


class DeliveryResult(BaseModel):
    """Outcome of sending a single posting; recorded in delivery_log."""

    external_id: str
    status: str  # "sent" | "failed"
    error: str | None = None
