"""NotificationTarget request/response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TargetBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: str = Field(min_length=1, max_length=50)
    config: dict[str, Any] = Field(default_factory=dict)


class TargetCreate(TargetBase):
    pass


class TargetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    type: str | None = Field(default=None, min_length=1, max_length=50)
    config: dict[str, Any] | None = None


class TargetRead(TargetBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
