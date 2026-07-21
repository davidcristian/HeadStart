"""Logging configuration. Call `configure_logging()` once at process startup."""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings

_CONFIGURED = False

# "-" means "no active request/task" so the formatter always has a field.
_request_id: ContextVar[str] = ContextVar("request_id", default="-")

# LogRecord attributes that are not application extras (JSON fields).
_STANDARD_RECORD_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "process",
        "processName",
        "message",
        "asctime",
        "taskName",
        "request_id",
    }
)

_TEXT_FORMAT = "%(asctime)s %(levelname)s %(name)s [%(request_id)s] :: %(message)s"
_TEXT_DATEFMT = "%Y-%m-%dT%H:%M:%S%z"


def get_request_id() -> str:
    """Return the active request/task correlation id, or '-' when unbound."""
    return _request_id.get()


def set_request_id(request_id: str) -> None:
    """Bind a correlation id for the current context (HTTP request or Celery task)."""
    _request_id.set(request_id)


def reset_request_id() -> None:
    """Clear the correlation id after a request or task finishes."""
    _request_id.set("-")


class RequestIdFilter(logging.Filter):
    """Inject the active correlation id onto every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per line for machine-parseable CloudWatch/Loki queries."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_ATTRS or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def reset_logging_config() -> None:
    """Allow tests to re-run configure_logging against a fresh root logger."""
    global _CONFIGURED
    _CONFIGURED = False


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    if settings.log_format == "text":
        handler.setFormatter(logging.Formatter(fmt=_TEXT_FORMAT, datefmt=_TEXT_DATEFMT))
    else:
        handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)

    # Tame noisy third-party loggers.
    for noisy in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
