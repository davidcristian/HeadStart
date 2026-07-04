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
