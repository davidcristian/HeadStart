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
