"""Per-user overrides layered on global summary settings."""

from __future__ import annotations

from typing import Any

from app.core.crypto import DecryptionError, decrypt
from app.models.user import User

USER_SUMMARY_PROVIDERS: frozenset[str] = frozenset({"heuristic", "openai", "gemini", "anthropic"})

_PROVIDER_API_KEY_ATTR: dict[str, str] = {
    "openai": "openai_api_key",
    "gemini": "gemini_api_key",
    "anthropic": "anthropic_api_key",
}


class SummarySettingsOverlay:
    """Settings-like object that merges global config with per-user overrides."""

    def __init__(
        self,
        base: Any,
        *,
        summary_provider: str,
        api_key_overrides: dict[str, str],
    ) -> None:
        self._base = base
        self.summary_provider = summary_provider
        self._api_key_overrides = api_key_overrides

    def __getattr__(self, name: str) -> Any:
        if name in _PROVIDER_API_KEY_ATTR.values():
            for provider, attr in _PROVIDER_API_KEY_ATTR.items():
                if name == attr and provider in self._api_key_overrides:
                    return self._api_key_overrides[provider]
        return getattr(self._base, name)


def resolve_summary_settings(base: Any, user: User | None) -> Any:
    """Return effective summary settings for a pipeline run."""
    provider = str(getattr(base, "summary_provider", "heuristic"))
    if user is not None and user.summary_provider:
        provider = str(user.summary_provider)

    api_key_overrides: dict[str, str] = {}
    if user is not None and user.summary_api_key_ciphertext and provider in _PROVIDER_API_KEY_ATTR:
        try:
            api_key_overrides[provider] = decrypt(user.summary_api_key_ciphertext)
        except DecryptionError:
            api_key_overrides[provider] = ""

    base_provider = str(getattr(base, "summary_provider", "heuristic"))
    if (
        not api_key_overrides
        and provider == base_provider
        and (user is None or not user.summary_provider)
    ):
        return base

    return SummarySettingsOverlay(
        base,
        summary_provider=provider,
        api_key_overrides=api_key_overrides,
    )
