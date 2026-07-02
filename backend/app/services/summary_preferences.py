"""Read and update per-user AI summary provider preferences."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import encrypt
from app.core.exceptions import PlanLimitError, ValidationError
from app.core.plans import required_plan_phrase
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.summary_preferences import (
    SummaryPreferencesRead,
    SummaryPreferencesUpdate,
    SummaryProviderId,
    SummaryProviderOption,
)
from app.services.plan_limits import PlanLimitsService
from app.summarizers.runtime_settings import USER_SUMMARY_PROVIDERS, resolve_summary_settings

_PROVIDER_OPTIONS: tuple[SummaryProviderOption, ...] = (
    SummaryProviderOption(
        id="heuristic",
        label="Built-in",
        description="Offline filter-based blurbs — no API key required.",
        requires_api_key=False,
    ),
    SummaryProviderOption(
        id="openai",
        label="OpenAI",
        description="Natural-language blurbs via an OpenAI-compatible API.",
        requires_api_key=True,
    ),
    SummaryProviderOption(
        id="gemini",
        label="Google Gemini",
        description="Natural-language blurbs via the Gemini API.",
        requires_api_key=True,
    ),
    SummaryProviderOption(
        id="anthropic",
        label="Anthropic Claude",
        description="Natural-language blurbs via the Anthropic Messages API.",
        requires_api_key=True,
    ),
)


class SummaryPreferencesService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.limits = PlanLimitsService(session)

    def get(self, user: User) -> SummaryPreferencesRead:
        """Return summary preferences for the Settings UI."""
        enabled = self.limits.allows_summaries(user.id)
        effective = self._effective_provider(user)
        selected = self._selected_provider(user)
        return SummaryPreferencesRead(
            enabled=enabled,
            server_default_provider=str(settings.summary_provider),
            selected_provider=selected,
            effective_provider=effective,
            has_custom_api_key=bool(user.summary_api_key_ciphertext),
            providers=list(_PROVIDER_OPTIONS),
        )

    def update(self, user_id: int, data: SummaryPreferencesUpdate) -> SummaryPreferencesRead:
        """Patch the user's summary provider and optional API key."""
        user = self.users.get(user_id)
        if user is None:
            raise ValidationError("User not found.")
        self._require_summaries_enabled(user)

        fields_set = data.model_fields_set
        if "provider" in fields_set:
            if data.provider is None:
                user.summary_provider = None
            else:
                self._validate_provider(data.provider)
                user.summary_provider = data.provider

        if "api_key" in fields_set:
            if data.api_key is None:
                pass
            elif data.api_key.strip() == "":
                user.summary_api_key_ciphertext = None
            else:
                user.summary_api_key_ciphertext = encrypt(data.api_key.strip())

        self.session.flush()
        return self.get(user)

    def _require_summaries_enabled(self, user: User) -> None:
        if not self.limits.allows_summaries(user.id):
            raise PlanLimitError(
                f"AI summaries require a {required_plan_phrase('pro')} plan.",
                code="feature_ai_summaries",
                plan=self.limits.resolve_plan(user),
            )

    def _validate_provider(self, provider: SummaryProviderId) -> None:
        if provider not in USER_SUMMARY_PROVIDERS:
            raise ValidationError(f"Unknown summary provider: {provider}")

    def _selected_provider(self, user: User) -> SummaryProviderId | None:
        if not user.summary_provider:
            return None
        provider = str(user.summary_provider)
        if provider in USER_SUMMARY_PROVIDERS:
            return provider  # type: ignore[return-value]
        return None

    def _effective_provider(self, user: User) -> SummaryProviderId:
        resolved = resolve_summary_settings(settings, user)
        provider = str(resolved.summary_provider)
        if provider in USER_SUMMARY_PROVIDERS:
            return provider  # type: ignore[return-value]
        return "heuristic"
