"""Tests for per-purpose AI runtime settings."""

from app.ai.runtime_settings import resolve_ai_settings, resolve_provider_for_purpose
from app.core.crypto import encrypt
from app.models.user import User


class _Settings:
    def __init__(
        self,
        *,
        provider: str = "heuristic",
        openai_api_key: str = "",
        gemini_api_key: str = "",
        openai_model: str = "gpt-4o-mini",
        anthropic_model: str = "claude-3-5-haiku-latest",
    ) -> None:
        self.summary_provider = provider
        self.openai_api_key = openai_api_key
        self.gemini_api_key = gemini_api_key
        self.openai_model = openai_model
        self.anthropic_model = anthropic_model


def test_cover_letter_inherits_global_provider() -> None:
    user = User(email="pro@example.com", password_hash="x", summary_provider="anthropic")
    base = _Settings(provider="heuristic")

    provider = resolve_provider_for_purpose(base, user, "cover_letter")
    assert provider == "anthropic"


def test_cover_letter_uses_purpose_override() -> None:
    user = User(
        email="pro@example.com",
        password_hash="x",
        summary_provider="anthropic",
        ai_purpose_providers={"cover_letter": "openai"},
    )
    base = _Settings(provider="heuristic")

    provider = resolve_provider_for_purpose(base, user, "cover_letter")
    assert provider == "openai"


def test_cover_letter_model_override() -> None:
    user = User(
        email="pro@example.com",
        password_hash="x",
        summary_provider="openai",
        ai_purpose_models={"cover_letter": "gpt-4o"},
    )
    base = _Settings(provider="openai", openai_model="gpt-4o-mini")

    runtime = resolve_ai_settings(base, user, "cover_letter")
    assert runtime.openai_model == "gpt-4o"


def test_summary_ignores_purpose_provider_map() -> None:
    user = User(
        email="pro@example.com",
        password_hash="x",
        summary_provider="gemini",
        ai_purpose_providers={"cover_letter": "openai"},
    )
    base = _Settings(provider="heuristic")

    provider = resolve_provider_for_purpose(base, user, "summary")
    assert provider == "gemini"


def test_resolve_ai_settings_uses_user_api_key_when_provider_matches() -> None:
    """Stored key applies only when the purpose resolves to summary_provider."""
    user = User(
        email="pro@example.com",
        password_hash="x",
        summary_provider="openai",
        summary_api_key_ciphertext=encrypt("user-secret"),
    )
    base = _Settings(provider="heuristic", openai_api_key="server-secret")

    runtime = resolve_ai_settings(base, user, "cover_letter")
    assert runtime.summary_provider == "openai"
    assert runtime.openai_api_key == "user-secret"


def test_resolve_ai_settings_drops_user_key_on_crossed_provider() -> None:
    """Purpose override to another vendor must not receive the stored OpenAI key."""
    user = User(
        email="pro@example.com",
        password_hash="x",
        summary_provider="openai",
        summary_api_key_ciphertext=encrypt("openai-secret"),
        ai_purpose_providers={"email_draft": "gemini"},
    )
    base = _Settings(
        provider="heuristic",
        openai_api_key="server-openai",
        gemini_api_key="server-gemini",
    )

    runtime = resolve_ai_settings(base, user, "email_draft")
    assert runtime.summary_provider == "gemini"
    assert runtime.gemini_api_key == "server-gemini"
    assert runtime.openai_api_key == "server-openai"


def test_resolve_ai_settings_ignores_key_without_summary_provider() -> None:
    """A ciphertext with no owning provider is never attached to a purpose override."""
    user = User(
        email="pro@example.com",
        password_hash="x",
        ai_purpose_providers={"cover_letter": "openai"},
        summary_api_key_ciphertext=encrypt("user-secret"),
    )
    base = _Settings(provider="heuristic", openai_api_key="server-secret")

    runtime = resolve_ai_settings(base, user, "cover_letter")
    assert runtime.summary_provider == "openai"
    assert runtime.openai_api_key == "server-secret"
