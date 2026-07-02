"""Per-user AI summary provider preferences."""

from typing import Literal

from pydantic import BaseModel, Field

SummaryProviderId = Literal["heuristic", "openai", "gemini", "anthropic"]


class SummaryProviderOption(BaseModel):
    """One selectable summary provider for the Settings UI."""

    id: SummaryProviderId
    label: str
    description: str
    requires_api_key: bool


class SummaryPreferencesRead(BaseModel):
    """Current summary settings for the signed-in user."""

    enabled: bool
    server_default_provider: str
    selected_provider: SummaryProviderId | None = None
    effective_provider: SummaryProviderId
    has_custom_api_key: bool
    providers: list[SummaryProviderOption]


class SummaryPreferencesUpdate(BaseModel):
    """Patch summary provider and optional bring-your-own API key."""

    provider: SummaryProviderId | None = Field(
        default=None,
        description="Set a provider, or null to use the server default.",
    )
    api_key: str | None = Field(
        default=None,
        max_length=512,
        description="New API key for the selected hosted provider; empty string clears it.",
    )
