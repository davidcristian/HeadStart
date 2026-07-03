"""Branch coverage for AI runtime settings resolution."""

from __future__ import annotations

import pytest

from app.ai.runtime_settings import (
    AiSettingsOverlay,
    resolve_ai_settings,
    resolve_model_for_purpose,
    resolve_provider_for_purpose,
    resolve_summary_settings,
)
from app.core.crypto import encrypt
from app.models.user import User


class _Settings:
    def __init__(
        self,
        *,
        provider: str = "heuristic",
        openai_api_key: str = "",
        openai_model: str = "gpt-4o-mini",
        gemini_model: str = "gemini-1.5-flash",
        anthropic_model: str = "claude-3-5-haiku-latest",
        llamacpp_model: str = "local",
    ) -> None:
        self.summary_provider = provider
        self.openai_api_key = openai_api_key
        self.gemini_api_key = ""
        self.anthropic_api_key = ""
        self.openai_model = openai_model
        self.gemini_model = gemini_model
        self.anthropic_model = anthropic_model
        self.llamacpp_model = llamacpp_model
        self.other_attr = "base-value"


# ---- AiSettingsOverlay.__getattr__ ----


def test_overlay_returns_api_key_override() -> None:
    overlay = AiSettingsOverlay(
        _Settings(),
        summary_provider="openai",
        api_key_overrides={"openai": "user-key"},
        model_overrides={},
    )
    assert overlay.openai_api_key == "user-key"


def test_overlay_falls_through_to_base_for_api_key_without_override() -> None:
    """A key attr with no matching override falls back to the base settings value."""
    overlay = AiSettingsOverlay(
        _Settings(openai_api_key="base-key"),
        summary_provider="openai",
        api_key_overrides={},
        model_overrides={},
    )
    assert overlay.openai_api_key == "base-key"


def test_overlay_returns_model_override() -> None:
    overlay = AiSettingsOverlay(
        _Settings(),
        summary_provider="openai",
        api_key_overrides={},
        model_overrides={"openai": "gpt-4o"},
    )
    assert overlay.openai_model == "gpt-4o"


def test_overlay_model_attr_without_override_uses_base() -> None:
    overlay = AiSettingsOverlay(
        _Settings(openai_model="base-model"),
        summary_provider="openai",
        api_key_overrides={},
        model_overrides={},
    )
    assert overlay.openai_model == "base-model"


def test_overlay_unknown_attr_reads_base() -> None:
    overlay = AiSettingsOverlay(
        _Settings(),
        summary_provider="openai",
        api_key_overrides={},
        model_overrides={},
    )
    assert overlay.other_attr == "base-value"


# ---- purpose maps: non-dict raw values ----


def test_provider_map_ignores_non_dict() -> None:
    user = User(email="a@example.test", password_hash="x")
    user.ai_purpose_providers = ["not", "a", "dict"]  # type: ignore[assignment]
    assert resolve_provider_for_purpose(_Settings(), user, "cover_letter") == "heuristic"


def test_model_map_ignores_non_dict() -> None:
    user = User(email="b@example.test", password_hash="x")
    user.ai_purpose_models = "nope"  # type: ignore[assignment]
    model = resolve_model_for_purpose(_Settings(), user, "cover_letter", provider="openai")
    assert model == "gpt-4o-mini"


# ---- resolve_provider_for_purpose ----


def test_unknown_purpose_raises() -> None:
    with pytest.raises(ValueError, match="Unknown AI purpose"):
        resolve_provider_for_purpose(_Settings(), None, "bogus")  # type: ignore[arg-type]


def test_provider_defaults_to_base_when_no_user() -> None:
    assert resolve_provider_for_purpose(_Settings(provider="gemini"), None, "summary") == "gemini"


# ---- resolve_model_for_purpose: unknown provider ----


def test_model_for_unknown_provider_is_empty() -> None:
    assert resolve_model_for_purpose(_Settings(), None, "summary", provider="mystery") == ""


# ---- resolve_ai_settings ----


def test_decryption_failure_yields_empty_api_key() -> None:
    """A ciphertext that cannot be decrypted must not crash; it degrades to empty."""
    user = User(
        email="c@example.test",
        password_hash="x",
        summary_provider="openai",
        summary_api_key_ciphertext="not-a-valid-fernet-token",
    )
    runtime = resolve_ai_settings(_Settings(provider="openai"), user, "summary")
    assert runtime.openai_api_key == ""


def test_resolve_ai_settings_returns_base_when_no_overrides() -> None:
    base = _Settings(provider="heuristic")
    assert resolve_ai_settings(base, None, "summary") is base


def test_resolve_summary_settings_delegates() -> None:
    user = User(
        email="d@example.test",
        password_hash="x",
        summary_provider="openai",
        summary_api_key_ciphertext=encrypt("secret"),
    )
    runtime = resolve_summary_settings(_Settings(provider="heuristic"), user)
    assert runtime.summary_provider == "openai"
    assert runtime.openai_api_key == "secret"
