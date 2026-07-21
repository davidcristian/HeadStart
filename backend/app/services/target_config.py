"""Per-type NotificationTarget config validation at create/update."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.core import secret_policy
from app.core.exceptions import ValidationError
from app.core.outbound_url import UnsafeOutboundUrlError, assert_safe_outbound_url


def validate_target_config(target_type: str, config: dict[str, Any]) -> None:
    """Reject missing required keys and unsafe outbound URLs before persist."""
    validator = _VALIDATORS.get(target_type)
    if validator is None:
        raise ValidationError(
            f"No config validator for target type '{target_type}'. "
            f"Available: {sorted(_VALIDATORS)}"
        )
    validator(config)


def assert_all_notifiers_have_config_validators() -> None:
    """Fail closed if a built-in notifier lacks a write-time config check.

    Compares against `notifiers.adapters.__all__` (not the live registry) so
    ephemeral keys registered by unit tests cannot false-fail the gate.
    """
    from app.notifiers import adapters as notifier_adapters

    builtin = set(notifier_adapters.__all__)
    missing = sorted(builtin - set(_VALIDATORS))
    if missing:
        raise AssertionError(f"Notifier types missing config validators: {missing}")
    extra = sorted(set(_VALIDATORS) - builtin)
    if extra:
        raise AssertionError(f"Config validators for unknown notifier types: {extra}")


def _require_non_empty(config: dict[str, Any], key: str, target_label: str) -> str:
    value = config.get(key)
    if value is None or not str(value).strip():
        raise ValidationError(f"{target_label} target requires config.{key}")
    return str(value).strip()


def _require_safe_url(config: dict[str, Any], key: str, target_label: str) -> str:
    url = _require_non_empty(config, key, target_label)
    try:
        assert_safe_outbound_url(url)
    except UnsafeOutboundUrlError as exc:
        raise ValidationError(
            f"{target_label} config.{key} is not a safe outbound URL: {exc}"
        ) from exc
    return url


def _optional_safe_url(config: dict[str, Any], key: str, target_label: str) -> None:
    raw = config.get(key)
    if raw is None or not str(raw).strip():
        return
    try:
        assert_safe_outbound_url(str(raw).strip())
    except UnsafeOutboundUrlError as exc:
        raise ValidationError(
            f"{target_label} config.{key} is not a safe outbound URL: {exc}"
        ) from exc


def _validate_ntfy(config: dict[str, Any]) -> None:
    topic = config.get("topic")
    try:
        secret_policy.assert_ntfy_topic_not_guessable("" if topic is None else str(topic))
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    _optional_safe_url(config, "server_url", "ntfy")


def _validate_email(config: dict[str, Any]) -> None:
    _require_non_empty(config, "to", "email")


def _validate_slack(config: dict[str, Any]) -> None:
    _require_safe_url(config, "webhook_url", "slack")


def _validate_discord(config: dict[str, Any]) -> None:
    _require_safe_url(config, "webhook_url", "discord")


def _validate_telegram(config: dict[str, Any]) -> None:
    _require_non_empty(config, "bot_token", "telegram")
    _require_non_empty(config, "chat_id", "telegram")


def _validate_webhook(config: dict[str, Any]) -> None:
    _require_safe_url(config, "webhook_url", "webhook")


_VALIDATORS: dict[str, Callable[[dict[str, Any]], None]] = {
    "ntfy": _validate_ntfy,
    "email": _validate_email,
    "slack": _validate_slack,
    "discord": _validate_discord,
    "telegram": _validate_telegram,
    "webhook": _validate_webhook,
}
