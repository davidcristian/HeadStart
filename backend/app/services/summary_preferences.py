"""Read and update per-user AI provider preferences."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.purposes import AI_PURPOSES, OVERRIDABLE_AI_PURPOSES, AiPurposeId
from app.ai.runtime_settings import (
    USER_AI_PROVIDERS,
    resolve_model_for_purpose,
    resolve_provider_for_purpose,
)
from app.core.config import settings
from app.core.crypto import encrypt
from app.core.exceptions import PlanLimitError, ValidationError
from app.core.plans import required_plan_phrase
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.summary_preferences import (
    AiPurposeOption,
    PurposePreferencePatch,
    PurposePreferenceRead,
    SummaryPreferencesRead,
    SummaryPreferencesUpdate,
    SummaryProviderId,
    SummaryProviderOption,
)
from app.services.plan_limits import PlanLimitsService

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

_PURPOSE_OPTIONS: tuple[AiPurposeOption, ...] = (
    AiPurposeOption(
        id="summary",
        label="Job match summaries",
        description="Short “why this matches” blurbs in notifications and the Jobs feed.",
        overridable=False,
    ),
    AiPurposeOption(
        id="cover_letter",
        label="Cover letters",
        description="Tailored cover letters in the apply dialog and auto-apply pipeline.",
        overridable=True,
    ),
    AiPurposeOption(
        id="resume_curation",
        label="Resume curation",
        description="Future: tailor resume bullets to each posting before apply.",
        overridable=True,
    ),
    AiPurposeOption(
        id="email_classify",
        label="Inbox classification",
        description="Future: sort recruiter email into folders during dev inbox automation.",
        overridable=True,
    ),
    AiPurposeOption(
        id="email_draft",
        label="Email reply drafts",
        description="Future: draft follow-up replies to recruiter messages.",
        overridable=True,
    ),
)


class SummaryPreferencesService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.limits = PlanLimitsService(session)

    def get(self, user: User) -> SummaryPreferencesRead:
        """Return AI preferences for the Settings UI."""
        enabled = self.limits.allows_summaries(user.id)
        effective = self._effective_provider(user, "summary")
        selected = self._selected_provider(user)
        purpose_preferences = {
            purpose: self._purpose_read(user, purpose) for purpose in AI_PURPOSES
        }
        return SummaryPreferencesRead(
            enabled=enabled,
            server_default_provider=str(settings.summary_provider),
            selected_provider=selected,
            effective_provider=effective,
            has_custom_api_key=bool(user.summary_api_key_ciphertext),
            providers=list(_PROVIDER_OPTIONS),
            purposes=list(_PURPOSE_OPTIONS),
            purpose_preferences=purpose_preferences,
        )

    def update(self, user_id: int, data: SummaryPreferencesUpdate) -> SummaryPreferencesRead:
        """Patch the user's global and per-purpose AI settings."""
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

        if "purpose_preferences" in fields_set and data.purpose_preferences is not None:
            self._apply_purpose_patches(user, data.purpose_preferences)

        self.session.flush()
        return self.get(user)

    def _apply_purpose_patches(
        self,
        user: User,
        patches: dict[str, PurposePreferencePatch],
    ) -> None:
        providers = dict(user.ai_purpose_providers or {})
        models = dict(user.ai_purpose_models or {})

        for purpose_key, patch in patches.items():
            if purpose_key not in AI_PURPOSES:
                raise ValidationError(f"Unknown AI purpose: {purpose_key}")
            if purpose_key == "summary":
                raise ValidationError("Use the global provider field for job match summaries.")
            if purpose_key not in OVERRIDABLE_AI_PURPOSES:
                raise ValidationError(f"Purpose {purpose_key} cannot be overridden.")

            patch_fields = patch.model_fields_set
            if "provider" in patch_fields:
                if patch.provider is None:
                    providers.pop(purpose_key, None)
                else:
                    self._validate_provider(patch.provider)
                    providers[purpose_key] = patch.provider

            if "model" in patch_fields:
                if patch.model is None:
                    pass
                elif patch.model.strip() == "":
                    models.pop(purpose_key, None)
                else:
                    models[purpose_key] = patch.model.strip()

        user.ai_purpose_providers = providers or None
        user.ai_purpose_models = models or None

    def _require_summaries_enabled(self, user: User) -> None:
        if not self.limits.allows_summaries(user.id):
            raise PlanLimitError(
                f"AI summaries require a {required_plan_phrase('pro')} plan.",
                code="feature_ai_summaries",
                plan=self.limits.resolve_plan(user),
            )

    def _validate_provider(self, provider: SummaryProviderId) -> None:
        if provider not in USER_AI_PROVIDERS:
            raise ValidationError(f"Unknown AI provider: {provider}")

    def _selected_provider(self, user: User) -> SummaryProviderId | None:
        if not user.summary_provider:
            return None
        provider = str(user.summary_provider)
        if provider in USER_AI_PROVIDERS:
            return provider  # type: ignore[return-value]
        return None

    def _selected_purpose_provider(
        self, user: User, purpose: AiPurposeId
    ) -> SummaryProviderId | None:
        if purpose == "summary":
            return self._selected_provider(user)
        raw = (user.ai_purpose_providers or {}).get(purpose)
        if not raw:
            return None
        provider = str(raw)
        if provider in USER_AI_PROVIDERS:
            return provider  # type: ignore[return-value]
        return None

    def _selected_purpose_model(self, user: User, purpose: AiPurposeId) -> str | None:
        raw = (user.ai_purpose_models or {}).get(purpose)
        if not raw:
            return None
        return str(raw)

    def _effective_provider(self, user: User, purpose: AiPurposeId) -> SummaryProviderId:
        provider = resolve_provider_for_purpose(settings, user, purpose)
        if provider in USER_AI_PROVIDERS:
            return provider  # type: ignore[return-value]
        return "heuristic"

    def _effective_model(self, user: User, purpose: AiPurposeId) -> str | None:
        provider = resolve_provider_for_purpose(settings, user, purpose)
        model = resolve_model_for_purpose(settings, user, purpose, provider=provider)
        return model or None

    def _purpose_read(self, user: User, purpose: AiPurposeId) -> PurposePreferenceRead:
        return PurposePreferenceRead(
            selected_provider=self._selected_purpose_provider(user, purpose),
            effective_provider=self._effective_provider(user, purpose),
            selected_model=self._selected_purpose_model(user, purpose),
            effective_model=self._effective_model(user, purpose),
        )
