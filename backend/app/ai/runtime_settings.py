"""Per-user overrides layered on global AI settings."""

from __future__ import annotations

from typing import Any

from app.ai.purposes import AI_PURPOSES, AiPurposeId
from app.core.crypto import DecryptionError, decrypt
from app.models.user import User

USER_AI_PROVIDERS: frozenset[str] = frozenset({"heuristic", "openai", "gemini", "anthropic"})

_PROVIDER_API_KEY_ATTR: dict[str, str] = {
    "openai": "openai_api_key",
    "gemini": "gemini_api_key",
    "anthropic": "anthropic_api_key",
}

_PROVIDER_MODEL_ATTR: dict[str, str] = {
    "openai": "openai_model",
    "gemini": "gemini_model",
    "anthropic": "anthropic_model",
    "llamacpp": "llamacpp_model",
}


class AiSettingsOverlay:
    """Settings-like object that merges global config with per-user overrides."""

    def __init__(
        self,
        base: Any,
        *,
        summary_provider: str,
        api_key_overrides: dict[str, str],
        model_overrides: dict[str, str],
    ) -> None:
        self._base = base
        self.summary_provider = summary_provider
        self._api_key_overrides = api_key_overrides
        self._model_overrides = model_overrides

    def __getattr__(self, name: str) -> Any:
        if name in _PROVIDER_API_KEY_ATTR.values():
            for provider, attr in _PROVIDER_API_KEY_ATTR.items():
                if name == attr and provider in self._api_key_overrides:
                    return self._api_key_overrides[provider]
        if name in _PROVIDER_MODEL_ATTR.values():
            for provider, attr in _PROVIDER_MODEL_ATTR.items():
                if name == attr and provider in self._model_overrides:
                    return self._model_overrides[provider]
        return getattr(self._base, name)


def _purpose_provider_map(user: User | None) -> dict[str, str]:
    if user is None or not user.ai_purpose_providers:
        return {}
    raw = user.ai_purpose_providers
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items() if value}


def _purpose_model_map(user: User | None) -> dict[str, str]:
    if user is None or not user.ai_purpose_models:
        return {}
    raw = user.ai_purpose_models
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items() if value}


def resolve_provider_for_purpose(base: Any, user: User | None, purpose: AiPurposeId) -> str:
    """Return the provider key for one AI purpose."""
    if purpose not in AI_PURPOSES:
        raise ValueError(f"Unknown AI purpose: {purpose}")

    if purpose != "summary":
        override = _purpose_provider_map(user).get(purpose)
        if override:
            return override

    if user is not None and user.summary_provider:
        return str(user.summary_provider)

    return str(getattr(base, "summary_provider", "heuristic"))


def resolve_model_for_purpose(
    base: Any,
    user: User | None,
    purpose: AiPurposeId,
    *,
    provider: str,
) -> str:
    """Return the model id for one AI purpose and provider."""
    override = _purpose_model_map(user).get(purpose)
    if override:
        return override
    attr = _PROVIDER_MODEL_ATTR.get(provider)
    if attr:
        return str(getattr(base, attr, ""))
    return ""


def resolve_ai_settings(base: Any, user: User | None, purpose: AiPurposeId = "summary") -> Any:
    """Return effective AI settings for one purpose."""
    provider = resolve_provider_for_purpose(base, user, purpose)

    api_key_overrides: dict[str, str] = {}
    if user is not None and user.summary_api_key_ciphertext and provider in _PROVIDER_API_KEY_ATTR:
        try:
            api_key_overrides[provider] = decrypt(user.summary_api_key_ciphertext)
        except DecryptionError:
            api_key_overrides[provider] = ""

    model_overrides: dict[str, str] = {}
    model = resolve_model_for_purpose(base, user, purpose, provider=provider)
    model_attr = _PROVIDER_MODEL_ATTR.get(provider)
    if model_attr and model and model != str(getattr(base, model_attr, "")):
        model_overrides[provider] = model

    has_purpose_provider_override = (
        user is not None and purpose != "summary" and purpose in _purpose_provider_map(user)
    )
    has_model_override = user is not None and purpose in _purpose_model_map(user)
    has_user_global = user is not None and bool(user.summary_provider)

    if (
        not api_key_overrides
        and not has_model_override
        and not has_purpose_provider_override
        and not (has_user_global and purpose == "summary")
        and provider == str(getattr(base, "summary_provider", "heuristic"))
    ):
        return base

    return AiSettingsOverlay(
        base,
        summary_provider=provider,
        api_key_overrides=api_key_overrides,
        model_overrides=model_overrides,
    )


def resolve_summary_settings(base: Any, user: User | None) -> Any:
    """Return effective summary settings for a pipeline run."""
    return resolve_ai_settings(base, user, "summary")
