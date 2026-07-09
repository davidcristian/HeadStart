"""HTTP security response headers for the API (AUT-23).

The SPA already sets these via nginx (XCT-16 / FRO-11). The API is a separate
origin behind the ALB, so it needs its own middleware — nothing else adds
HSTS/nosniff/framing/referrer hardening on JSON or /docs responses.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings
from app.core.secret_policy import is_local_environment

# Match the SPA nginx values so both origins share one hardening baseline.
X_CONTENT_TYPE_OPTIONS = "nosniff"
X_FRAME_OPTIONS = "DENY"
REFERRER_POLICY = "strict-origin-when-cross-origin"
# One year; includeSubDomains covers api.<host> when the cert is shared.
HSTS_VALUE = "max-age=31536000; includeSubDomains"
# Minimal CSP for an API that may still serve HTML (/docs): block framing.
CSP_FRAME_ANCESTORS = "frame-ancestors 'none'"


def apply_security_headers(response: Response, *, include_hsts: bool) -> None:
    """Stamp baseline security headers onto an HTTP response."""
    response.headers.setdefault("X-Content-Type-Options", X_CONTENT_TYPE_OPTIONS)
    response.headers.setdefault("X-Frame-Options", X_FRAME_OPTIONS)
    response.headers.setdefault("Referrer-Policy", REFERRER_POLICY)
    response.headers.setdefault("Content-Security-Policy", CSP_FRAME_ANCESTORS)
    if include_hsts:
        response.headers.setdefault("Strict-Transport-Security", HSTS_VALUE)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach browser hardening headers to every API response."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        # Skip HSTS on local/test HTTP so browsers do not pin localhost to HTTPS.
        include_hsts = not is_local_environment(get_settings().environment)
        apply_security_headers(response, include_hsts=include_hsts)
        return response
