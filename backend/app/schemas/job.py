"""Job feed (seen job) response schema."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    search_id: int
    external_id: str
    title: str
    company: str
    location: str
    url: str
    first_seen_at: datetime
