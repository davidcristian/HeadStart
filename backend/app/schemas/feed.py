"""RSS feed request/response schemas."""

from pydantic import BaseModel, Field


class FeedUrlRead(BaseModel):
    url: str = Field(description="Absolute RSS feed URL including the signed token")
    token: str = Field(description="Signed feed token (also embedded in url)")
