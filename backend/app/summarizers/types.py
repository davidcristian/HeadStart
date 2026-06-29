"""Shared summarizer data types."""

from typing import Any

from pydantic import BaseModel, Field


class SummaryContext(BaseModel):
    """Everything a summarizer needs to explain why a job matches a search."""

    search_name: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
