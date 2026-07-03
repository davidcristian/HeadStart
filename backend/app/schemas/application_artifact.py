"""Application artifact request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApplicationArtifactMeta(BaseModel):
    """Metadata for a stored generated document (no raw bytes)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    artifact_type: str
    filename: str
    content_type: str
    size_bytes: int = Field(ge=0)
    content_sha256: str
    created_at: datetime
