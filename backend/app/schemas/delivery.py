"""Delivery log read schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DeliveryFailureRead(BaseModel):
    """A recent failed notification attempt for a search."""

    model_config = ConfigDict(from_attributes=True)

    job_title: str
    job_url: str
    error: str | None
    sent_at: datetime
