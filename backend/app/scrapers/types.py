"""Shared scraper data types.

`JobPosting` is the normalized shape every adapter must return, so the rest of
the system never depends on a site's specific payload.
"""

from datetime import datetime
from hashlib import sha256
from typing import Any

from pydantic import BaseModel, Field


class JobPosting(BaseModel):
    external_id: str
    title: str
    company: str = ""
    location: str = ""
    url: str = ""
    posted_at: datetime | None = None
    # A short "why this matches" blurb generated after scraping (see
    # app/summarizers/). Not part of the identity hash; purely presentational.
    summary: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)

    def content_hash(self) -> str:
        """Stable hash of the identifying fields, used for change detection."""
        basis = f"{self.external_id}|{self.title}|{self.company}|{self.location}|{self.url}"
        return sha256(basis.encode("utf-8")).hexdigest()


class ScrapeContext(BaseModel):
    """Everything an adapter needs to perform one fetch for a search.

    `cookies`/`headers` carry per-site session material decrypted from the
    owner's SiteCredential (when present); they are also applied to the shared
    HttpClient so adapters generally don't need to read them directly.
    """

    query_url: str = ""
    filters: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    cookies: dict[str, str] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
