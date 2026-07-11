"""Tests for startup secret / SMTP policy helpers."""

from __future__ import annotations

import pytest

from app.core import secret_policy


@pytest.mark.parametrize(
    ("environment", "expected"),
    [
        ("local", True),
        ("LOCAL", True),
        (" test ", True),
        ("production", False),
        ("staging", False),
    ],
)
def test_is_local_environment(environment: str, expected: bool) -> None:
    assert secret_policy.is_local_environment(environment) is expected


def test_assert_smtp_configured_allows_local_without_host() -> None:
    secret_policy.assert_smtp_configured_for_environment("local", "")
    secret_policy.assert_smtp_configured_for_environment("test", "  ")


def test_assert_smtp_configured_allows_non_local_with_host() -> None:
    secret_policy.assert_smtp_configured_for_environment("production", "smtp.example.com")


def test_assert_smtp_configured_rejects_non_local_without_host() -> None:
    with pytest.raises(ValueError, match="SMTP_HOST"):
        secret_policy.assert_smtp_configured_for_environment("production", "")


def test_assert_ntfy_topic_allows_local_placeholder() -> None:
    secret_policy.assert_ntfy_topic_safe_for_environment(
        "local", secret_policy.DEV_NTFY_DEFAULT_TOPIC
    )
    secret_policy.assert_ntfy_topic_safe_for_environment("test", "")


def test_assert_ntfy_topic_allows_non_local_unique() -> None:
    secret_policy.assert_ntfy_topic_safe_for_environment("production", "jobs-a1b2c3d4e5f67890")


def test_assert_ntfy_topic_rejects_placeholder_outside_local() -> None:
    with pytest.raises(ValueError, match="NTFY_DEFAULT_TOPIC"):
        secret_policy.assert_ntfy_topic_safe_for_environment(
            "production", secret_policy.DEV_NTFY_DEFAULT_TOPIC
        )


def test_assert_ntfy_topic_rejects_blank_outside_local() -> None:
    with pytest.raises(ValueError, match="NTFY_DEFAULT_TOPIC"):
        secret_policy.assert_ntfy_topic_safe_for_environment("staging", "  ")


def test_assert_ntfy_topic_rejects_change_me_substring() -> None:
    with pytest.raises(ValueError, match="NTFY_DEFAULT_TOPIC"):
        secret_policy.assert_ntfy_topic_safe_for_environment("production", "alerts-CHANGE-ME-now")


def test_assert_ntfy_topic_rejects_short_outside_local() -> None:
    """NTF-06: non-local boots also reject under-length topics."""
    with pytest.raises(ValueError, match="NTFY_DEFAULT_TOPIC"):
        secret_policy.assert_ntfy_topic_safe_for_environment("production", "short-topic")


def test_is_guessable_ntfy_topic() -> None:
    assert secret_policy.is_guessable_ntfy_topic("") is True
    assert secret_policy.is_guessable_ntfy_topic("  ") is True
    assert secret_policy.is_guessable_ntfy_topic(secret_policy.DEV_NTFY_DEFAULT_TOPIC) is True
    assert secret_policy.is_guessable_ntfy_topic("my-change-me-topic") is True
    assert secret_policy.is_guessable_ntfy_topic("too-short") is True
    assert secret_policy.is_guessable_ntfy_topic("jobs-a1b2c3d4e5f67890") is False


def test_assert_ntfy_topic_not_guessable() -> None:
    secret_policy.assert_ntfy_topic_not_guessable("jobs-a1b2c3d4e5f67890")
    with pytest.raises(ValueError, match="unguessable"):
        secret_policy.assert_ntfy_topic_not_guessable("headstart-change-me")


def test_generate_ntfy_topic_is_unguessable() -> None:
    topic = secret_policy.generate_ntfy_topic()
    assert topic.startswith("jobs-")
    assert secret_policy.is_guessable_ntfy_topic(topic) is False
    assert topic != secret_policy.generate_ntfy_topic()


def test_assert_boot_safe_runs_all_guards() -> None:
    secret_policy.assert_boot_safe_for_environment(
        "production",
        "a-real-long-random-production-secret-value",
        "another-real-production-fernet-value",
        "smtp.example.com",
        "jobs-a1b2c3d4e5f67890",
        auth_cookie_secure=True,
        auth_cookie_samesite="lax",
        frontend_base_url="https://app.example.com",
    )
    with pytest.raises(ValueError, match="NTFY_DEFAULT_TOPIC"):
        secret_policy.assert_boot_safe_for_environment(
            "production",
            "a-real-long-random-production-secret-value",
            "another-real-production-fernet-value",
            "smtp.example.com",
            secret_policy.DEV_NTFY_DEFAULT_TOPIC,
            auth_cookie_secure=True,
            auth_cookie_samesite="lax",
            frontend_base_url="https://app.example.com",
        )


def test_assert_auth_cookie_allows_local_incoherent_combo() -> None:
    """local/test keep convenient defaults (Secure + http localhost)."""
    secret_policy.assert_auth_cookie_coherent_for_environment(
        "local",
        True,
        "lax",
        "http://localhost:5173",
    )
    secret_policy.assert_auth_cookie_coherent_for_environment(
        "test",
        False,
        "none",
        "http://localhost:5173",
    )


def test_assert_auth_cookie_rejects_secure_with_http_frontend() -> None:
    with pytest.raises(ValueError, match="AUTH_COOKIE_SECURE"):
        secret_policy.assert_auth_cookie_coherent_for_environment(
            "production",
            True,
            "lax",
            "http://app.example.com",
        )


def test_assert_auth_cookie_rejects_samesite_none_without_secure() -> None:
    with pytest.raises(ValueError, match="AUTH_COOKIE_SAMESITE"):
        secret_policy.assert_auth_cookie_coherent_for_environment(
            "staging",
            False,
            "None",
            "https://app.example.com",
        )


def test_assert_auth_cookie_allows_secure_https_and_http_insecure() -> None:
    secret_policy.assert_auth_cookie_coherent_for_environment(
        "production",
        True,
        "none",
        "https://app.example.com",
    )
    secret_policy.assert_auth_cookie_coherent_for_environment(
        "production",
        False,
        "lax",
        "http://alb.example.com",
    )


def test_assert_boot_safe_rejects_incoherent_cookie_flags() -> None:
    with pytest.raises(ValueError, match="AUTH_COOKIE_SECURE"):
        secret_policy.assert_boot_safe_for_environment(
            "production",
            "a-real-long-random-production-secret-value",
            "another-real-production-fernet-value",
            "smtp.example.com",
            "jobs-a1b2c3d4e5f67890",
            auth_cookie_secure=True,
            auth_cookie_samesite="lax",
            frontend_base_url="http://app.example.com",
        )


def test_assert_secrets_rejects_short_credentials_key() -> None:
    """Non-local boots reject a non-placeholder key that is still too short (AUT-05)."""
    with pytest.raises(ValueError, match="at least 32"):
        secret_policy.assert_secrets_safe_for_environment(
            "production",
            "a-real-long-random-production-secret-value",
            "too-short-to-be-safe",
        )


def test_assert_secrets_allows_long_non_placeholder_key() -> None:
    secret_policy.assert_secrets_safe_for_environment(
        "production",
        "a-real-long-random-production-secret-value",
        "another-real-production-fernet-value",
    )
