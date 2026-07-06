"""API schemas for inbox reply send audit logs."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ReplySendLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    inbox_reply_draft_id: int
    inbox_pending_reply_id: int | None = None
    outcome: str
    reason: str
    subject: str
    body_excerpt: str
    payload: dict[str, Any] | None = None
    created_at: datetime
