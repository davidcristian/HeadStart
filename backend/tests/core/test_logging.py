"""Tests for JSON / text logging configuration."""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest

from app.core import logging as logging_module
from app.core.logging import (
    JsonFormatter,
    RequestIdFilter,
    configure_logging,
    reset_logging_config,
    reset_request_id,
    set_request_id,
)


@pytest.fixture(autouse=True)
def _reset_logging_state() -> None:
    reset_logging_config()
    reset_request_id()
    yield
    reset_logging_config()
    reset_request_id()
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.WARNING)


def test_json_formatter_emits_parseable_fields() -> None:
    set_request_id("corr-1")
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    RequestIdFilter().filter(record)
    record.auth_event = "login_success"
    record.user_id = 42

    payload = json.loads(JsonFormatter().format(record))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert payload["request_id"] == "corr-1"
    assert payload["message"] == "hello world"
    assert payload["auth_event"] == "login_success"
    assert payload["user_id"] == 42
    assert payload["timestamp"].endswith("Z")
    assert "exc_info" not in payload


def test_json_formatter_includes_exc_info() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        exc_info = sys.exc_info()
    record = logging.LogRecord(
        name="app.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="failed",
        args=(),
        exc_info=exc_info,
    )
    RequestIdFilter().filter(record)
    payload = json.loads(JsonFormatter().format(record))
    assert "ValueError: boom" in payload["exc_info"]


def test_json_formatter_skips_private_record_attrs() -> None:
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="x",
        args=(),
        exc_info=None,
    )
    RequestIdFilter().filter(record)
    record._private = "secret"  # type: ignore[attr-defined]
    record.public_extra = "ok"  # type: ignore[attr-defined]
    payload = json.loads(JsonFormatter().format(record))
    assert "_private" not in payload
    assert payload["public_extra"] == "ok"


def test_get_logger_returns_named_logger() -> None:
    from app.core.logging import get_logger

    assert get_logger("app.core.logging_probe").name == "app.core.logging_probe"


def test_configure_logging_unknown_level_falls_back_to_info(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        logging_module,
        "settings",
        SimpleNamespace(log_level="not-a-level", log_format="json"),
    )
    configure_logging()
    assert logging.getLogger().level == logging.INFO


def test_configure_logging_json_is_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        logging_module,
        "settings",
        SimpleNamespace(log_level="INFO", log_format="json"),
    )
    configure_logging()
    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, JsonFormatter)
    # Second call is a no-op.
    configure_logging()
    assert len(root.handlers) == 1


def test_configure_logging_text_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        logging_module,
        "settings",
        SimpleNamespace(log_level="DEBUG", log_format="text"),
    )
    configure_logging()
    formatter = logging.getLogger().handlers[0].formatter
    assert isinstance(formatter, logging.Formatter)
    assert not isinstance(formatter, JsonFormatter)
    assert logging.getLogger().level == logging.DEBUG
