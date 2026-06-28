"""Site credential request/response schemas.

Secrets (cookies/headers/session) are accepted on write but NEVER returned on
read. `CredentialRead` exposes only metadata plus booleans indicating which
kinds of secret material are stored.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CredentialBase(BaseModel):
    source_id: int
    name: str = Field(default="", max_length=200)
    enabled: bool = True


class CredentialCreate(CredentialBase):
    cookies: dict[str, str] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    session: dict[str, str] = Field(default_factory=dict)


class CredentialUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    enabled: bool | None = None
    # When provided, the secret payload is replaced wholesale.
    cookies: dict[str, str] | None = None
    headers: dict[str, str] | None = None
    session: dict[str, str] | None = None


class CredentialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    name: str
    enabled: bool
    created_at: datetime
    has_cookies: bool = False
    has_headers: bool = False
    has_session: bool = False
