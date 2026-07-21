"""HTTP and Celery correlation-id binding for structured triage."""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import reset_request_id, set_request_id

REQUEST_ID_HEADER = "X-Request-ID"
# Clients may pass a UUID or opaque token; reject anything that would break logs.
_MAX_REQUEST_ID_LEN = 128
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def resolve_request_id(raw: str | None) -> str:
    """Accept a well-formed client id or mint a new UUID4."""
    if raw is None:
        return str(uuid.uuid4())
    candidate = raw.strip()
    if (
        candidate
        and len(candidate) <= _MAX_REQUEST_ID_LEN
        and _REQUEST_ID_RE.fullmatch(candidate) is not None
    ):
        return candidate
    return str(uuid.uuid4())


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Bind a per-request correlation id and echo it on the response."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
        set_request_id(request_id)
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            reset_request_id()


def bind_celery_task_id(task_id: str | None) -> None:
    """Use the Celery task id as the correlation id for worker log lines."""
    if task_id:
        set_request_id(task_id)
    else:
        reset_request_id()
