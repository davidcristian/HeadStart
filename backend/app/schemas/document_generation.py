"""Document generation (async resume / cover-letter) request/response schemas."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DocumentGenerationKind = Literal["resume", "cover_letter"]
DocumentGenerationStatus = Literal["queued", "processing", "ready", "failed"]


class DocumentGenerationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: DocumentGenerationKind
    status: DocumentGenerationStatus
    error: str | None = None
    result: dict[str, Any] | None = Field(
        default=None,
        description="Kind-specific payload when status is ready (resume or cover letter fields)",
    )
    created_at: datetime
    updated_at: datetime
