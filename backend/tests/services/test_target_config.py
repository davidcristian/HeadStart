"""Unit tests for per-type notification target config validation."""

from unittest.mock import patch

import pytest

from app.core.exceptions import ValidationError
from app.services import target_config
from app.services.target_config import (
    assert_all_notifiers_have_config_validators,
    validate_target_config,
)

_SAFE_TOPIC = "jobs-a1b2c3d4e5f67890"
_SAFE_WEBHOOK = "https://hooks.example/services/T00/B00/xxxx"


def test_every_registered_notifier_has_a_config_validator() -> None:
    assert_all_notifiers_have_config_validators()


def test_unknown_type_has_no_validator() -> None:
    with pytest.raises(ValidationError, match="No config validator"):
        validate_target_config("carrier-pigeon", {})


def test_assert_missing_validator_raises() -> None:
    with (
        patch.dict(target_config._VALIDATORS, clear=True),
        pytest.raises(AssertionError, match="missing config validators"),
    ):
        assert_all_notifiers_have_config_validators()


def test_assert_extra_validator_raises() -> None:
    with (
        patch.dict(
            target_config._VALIDATORS,
            {"ghost_channel": lambda _c: None},
            clear=False,
        ),
        pytest.raises(AssertionError, match="unknown notifier types"),
    ):
        assert_all_notifiers_have_config_validators()


def test_ntfy_accepts_unguessable_topic() -> None:
    validate_target_config("ntfy", {"topic": _SAFE_TOPIC})
    validate_target_config("ntfy", {"topic": _SAFE_TOPIC, "server_url": "https://ntfy.example"})


def test_ntfy_rejects_guessable_topic() -> None:
    with pytest.raises(ValidationError, match="unguessable"):
        validate_target_config("ntfy", {"topic": "headstart-change-me"})


def test_ntfy_rejects_private_server_url() -> None:
    with pytest.raises(ValidationError, match="safe outbound URL"):
        validate_target_config(
            "ntfy",
            {"topic": _SAFE_TOPIC, "server_url": "http://127.0.0.1:2586"},
        )


def test_ntfy_ignores_blank_server_url() -> None:
    validate_target_config("ntfy", {"topic": _SAFE_TOPIC, "server_url": "  "})


def test_email_requires_to() -> None:
    with pytest.raises(ValidationError, match="config.to"):
        validate_target_config("email", {})
    validate_target_config("email", {"to": "you@example.com"})


def test_slack_requires_safe_webhook_url() -> None:
    with pytest.raises(ValidationError, match="config.webhook_url"):
        validate_target_config("slack", {})
    with pytest.raises(ValidationError, match="safe outbound URL"):
        validate_target_config("slack", {"webhook_url": "http://127.0.0.1/hook"})
    validate_target_config("slack", {"webhook_url": _SAFE_WEBHOOK})


def test_discord_requires_safe_webhook_url() -> None:
    with pytest.raises(ValidationError, match="config.webhook_url"):
        validate_target_config("discord", {})
    validate_target_config("discord", {"webhook_url": _SAFE_WEBHOOK})


def test_telegram_requires_token_and_chat() -> None:
    with pytest.raises(ValidationError, match="config.bot_token"):
        validate_target_config("telegram", {"chat_id": "1"})
    with pytest.raises(ValidationError, match="config.chat_id"):
        validate_target_config("telegram", {"bot_token": "123:ABC"})
    validate_target_config("telegram", {"bot_token": "123:ABC", "chat_id": "99"})


def test_webhook_requires_safe_webhook_url() -> None:
    with pytest.raises(ValidationError, match="config.webhook_url"):
        validate_target_config("webhook", {})
    with pytest.raises(ValidationError, match="safe outbound URL"):
        validate_target_config("webhook", {"webhook_url": "http://169.254.169.254/"})
    validate_target_config("webhook", {"webhook_url": "https://hooks.example/headstart"})
