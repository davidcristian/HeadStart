"""API schemas for inbox folder / label routing."""

from pydantic import BaseModel, Field

from app.inbox.routing import InboxRoutingConfig


class InboxRoutingConfigRead(InboxRoutingConfig):
    """Resolved routing config returned to the client."""


class InboxRoutingConfigUpdate(BaseModel):
    """Partial update for label→folder routing."""

    enabled: bool | None = None
    auto_route_on_classify: bool | None = None
    label_folders: dict[str, str] | None = None
    sender_allowlist: list[str] | None = None


class InboxRouteRequest(BaseModel):
    """Route one classified message into its configured folder."""

    classification_id: int | None = Field(default=None, ge=1)
    message_uid: int | None = Field(default=None, ge=1)


class InboxRouteResponse(BaseModel):
    classification_id: int
    message_uid: int
    label: str
    routing_status: str
    routed_to: str | None = None
    routing_error: str | None = None
