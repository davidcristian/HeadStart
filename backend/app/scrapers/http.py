"""Small synchronous HTTP helper shared by scrapers.

Centralizes the User-Agent, timeouts, redirect policy, and response body-size
cap so individual adapters stay focused on parsing.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.outbound_http import apply_outbound_pin
from app.core.outbound_url import assert_safe_outbound_url
from app.scrapers.rate_limit import RateLimiter

DEFAULT_USER_AGENT = "HeadStart/0.1 (+https://github.com/; polite job-posting watcher)"
DEFAULT_TIMEOUT = 20.0
# Job-board HTML/JSON pages are typically well under this; a hostile upstream
# that streams multi-GB bodies must not OOM a shared Celery worker.
DEFAULT_MAX_RESPONSE_BYTES = 5_242_880  # 5 MiB


class ResponseTooLargeError(ValueError):
    """Upstream response exceeded the scraper body-size cap."""


def _prepare_outbound_request(request: httpx.Request) -> None:
    apply_outbound_pin(request)


def _declared_content_length(headers: httpx.Headers) -> int | None:
    raw = headers.get("content-length")
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    if value < 0:
        return None
    return value


def _read_body_limited(response: httpx.Response, max_bytes: int) -> bytes:
    """Stream a response body, aborting once it exceeds ``max_bytes``."""
    declared = _declared_content_length(response.headers)
    if declared is not None and declared > max_bytes:
        response.close()
        raise ResponseTooLargeError(
            f"Response Content-Length {declared} exceeds limit of {max_bytes} bytes"
        )
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            response.close()
            raise ResponseTooLargeError(f"Response body exceeds limit of {max_bytes} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def _limited_response(response: httpx.Response, max_bytes: int) -> httpx.Response:
    """Return a closed Response whose body was read under the size cap."""
    body = _read_body_limited(response, max_bytes)
    return httpx.Response(
        status_code=response.status_code,
        headers=response.headers,
        content=body,
        request=response.request,
        extensions=response.extensions,
        history=response.history,
    )


class HttpClient:
    def __init__(
        self,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = DEFAULT_TIMEOUT,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        client: httpx.Client | None = None,
        rate_limiter: RateLimiter | None = None,
        max_response_bytes: int | None = None,
    ) -> None:
        self._owns_client = client is None
        self._rate_limiter = rate_limiter
        if max_response_bytes is None:
            # Lazy import keeps this module importable without loading settings.
            from app.core.config import get_settings

            self._max_response_bytes = get_settings().scraper_max_response_bytes
        else:
            self._max_response_bytes = max_response_bytes
        merged_headers = {"User-Agent": user_agent, **(headers or {})}
        self._client = client or httpx.Client(
            headers=merged_headers,
            cookies=cookies or {},
            timeout=timeout,
            follow_redirects=True,
            event_hooks={"request": [_prepare_outbound_request]},
        )

    def get_json(self, url: str, **kwargs: Any) -> Any:
        return self._stream_response("GET", url, **kwargs).json()

    def post_json(self, url: str, *, json: Any = None, **kwargs: Any) -> Any:
        return self._stream_response("POST", url, json=json, **kwargs).json()

    def post_form(self, url: str, *, data: dict[str, str], **kwargs: Any) -> str:
        """POST application/x-www-form-urlencoded and return the response text."""
        return self._stream_response("POST", url, data=data, **kwargs).text

    def post_raw(
        self,
        url: str,
        *,
        content: bytes | str = b"",
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """POST raw bytes and return the full HTTP response (for header-driven flows)."""
        return self._stream_response("POST", url, content=content, headers=headers, **kwargs)

    def put_json(self, url: str, *, json: Any = None, **kwargs: Any) -> Any:
        """PUT JSON and parse a JSON response body."""
        return self._stream_response("PUT", url, json=json, **kwargs).json()

    def put_raw(
        self,
        url: str,
        *,
        content: bytes | str = b"",
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """PUT raw bytes and return the full HTTP response (for signed upload URLs)."""
        return self._stream_response("PUT", url, content=content, headers=headers, **kwargs)

    def post_multipart(
        self, url: str, *, data: dict[str, Any], files: dict[str, Any], **kwargs: Any
    ) -> Any:
        """POST multipart/form-data; returns JSON when the response is JSON."""
        resp = self._stream_response("POST", url, data=data, files=files, **kwargs)
        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            return resp.json()
        return resp.text

    def get_text(self, url: str, **kwargs: Any) -> str:
        return self._stream_response("GET", url, **kwargs).text

    def _stream_response(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Send a request, stream the body under the size cap, return a buffered response."""
        self._wait_rate_limit()
        assert_safe_outbound_url(url)
        with self._client.stream(method, url, **kwargs) as resp:
            resp.raise_for_status()
            return _limited_response(resp, self._max_response_bytes)

    def _wait_rate_limit(self) -> None:
        if self._rate_limiter is not None:
            self._rate_limiter.wait()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
