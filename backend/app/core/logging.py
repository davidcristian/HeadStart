"""Logging configuration. Call `configure_logging()` once at process startup."""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

from app.core.config import settings

_CONFIGURED = False

# "-" means "no active request/task" so the formatter always has a field.
_request_id: ContextVar[str] = ContextVar("request_id", default="-")


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


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s [%(request_id)s] :: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)

    # Tame noisy third-party loggers.
    for noisy in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
