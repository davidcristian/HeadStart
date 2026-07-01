"""Helpers for extracting client metadata from HTTP requests."""

from __future__ import annotations

from dataclasses import dataclass

from starlette.requests import Request


@dataclass(frozen=True, slots=True)
class RequestMeta:
    ip_address: str | None
    user_agent: str | None


def request_meta(request: Request) -> RequestMeta:
    """Best-effort client IP and user agent for audit logging."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip_address = forwarded.split(",")[0].strip() or None
    elif request.client is not None:
        ip_address = request.client.host
    else:
        ip_address = None
    user_agent = request.headers.get("user-agent")
    return RequestMeta(ip_address=ip_address, user_agent=user_agent)
