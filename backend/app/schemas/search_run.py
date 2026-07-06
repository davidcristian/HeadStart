"""Search run (async manual pipeline) request/response schemas."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

SearchRunStatus = Literal["queued", "processing", "ready", "failed"]


class SearchRunRead(BaseModel):
    """Queued or completed manual search run for polling."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    search_id: int
    status: SearchRunStatus
    found: int = 0
    new: int = 0
    notified: int = 0
    failed: int = 0
    skipped: int = 0
    filtered: int = 0
    queued: int = 0
    closed: int = 0
    error: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: Any) -> "SearchRunRead":
        """Flatten stored result counts onto the poll response."""
        counts = row.result if isinstance(row.result, dict) else {}
        return cls(
            id=row.id,
            search_id=row.search_id,
            status=row.status,
            found=int(counts.get("found", 0)),
            new=int(counts.get("new", 0)),
            notified=int(counts.get("notified", 0)),
            failed=int(counts.get("failed", 0)),
            skipped=int(counts.get("skipped", 0)),
            filtered=int(counts.get("filtered", 0)),
            queued=int(counts.get("queued", 0)),
            closed=int(counts.get("closed", 0)),
            error=row.error,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
