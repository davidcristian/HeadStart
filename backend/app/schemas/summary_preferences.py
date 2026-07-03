"""Per-user AI provider preferences."""

from typing import Literal

from pydantic import BaseModel, Field

from app.ai.purposes import AiPurposeId

SummaryProviderId = Literal["heuristic", "openai", "gemini", "anthropic"]


class SummaryProviderOption(BaseModel):
    """One selectable summary provider for the Settings UI."""

    id: SummaryProviderId
    label: str
    description: str
    requires_api_key: bool


class AiPurposeOption(BaseModel):
    """One AI task that can use its own provider/model."""

    id: AiPurposeId
    label: str
    description: str
    overridable: bool


class PurposePreferenceRead(BaseModel):
    """Effective and selected provider/model for one AI purpose."""

    selected_provider: SummaryProviderId | None = None
    effective_provider: SummaryProviderId
    selected_model: str | None = None
    effective_model: str | None = None


class SummaryPreferencesRead(BaseModel):
    """Current AI settings for the signed-in user."""

    enabled: bool
    server_default_provider: str
    selected_provider: SummaryProviderId | None = None
    effective_provider: SummaryProviderId
    has_custom_api_key: bool
    providers: list[SummaryProviderOption]
    purposes: list[AiPurposeOption]
    purpose_preferences: dict[str, PurposePreferenceRead]


class PurposePreferencePatch(BaseModel):
    """Patch one purpose's provider and optional model override."""

    provider: SummaryProviderId | None = Field(
        default=None,
        description="Set a provider, or null to inherit the global default.",
    )
    model: str | None = Field(
        default=None,
        max_length=128,
        description="Optional model id override; empty string clears it.",
    )


class SummaryPreferencesUpdate(BaseModel):
    """Patch global and per-purpose AI provider settings."""

    provider: SummaryProviderId | None = Field(
        default=None,
        description="Global default provider, or null to use the server default.",
    )
    api_key: str | None = Field(
        default=None,
        max_length=512,
        description="New API key for hosted providers; empty string clears it.",
    )
    purpose_preferences: dict[str, PurposePreferencePatch] | None = Field(
        default=None,
        description="Per-purpose overrides for cover letters and future agents.",
    )
