"""Small synchronous HTTP helper shared by scrapers.

Centralizes the User-Agent, timeouts, and redirect policy so individual
adapters stay focused on parsing.
"""

from typing import Any

import httpx

from app.core.outbound_url import assert_safe_outbound_url
from app.scrapers.rate_limit import RateLimiter

DEFAULT_USER_AGENT = "HeadStart/0.1 (+https://github.com/; polite job-posting watcher)"
DEFAULT_TIMEOUT = 20.0


def _validate_outbound_request(request: httpx.Request) -> None:
    assert_safe_outbound_url(str(request.url))


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
    ) -> None:
        self._owns_client = client is None
        self._rate_limiter = rate_limiter
        merged_headers = {"User-Agent": user_agent, **(headers or {})}
        self._client = client or httpx.Client(
            headers=merged_headers,
            cookies=cookies or {},
            timeout=timeout,
            follow_redirects=True,
            event_hooks={"request": [_validate_outbound_request]},
        )

    def get_json(self, url: str, **kwargs: Any) -> Any:
        self._wait_rate_limit()
        assert_safe_outbound_url(url)
        resp = self._client.get(url, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def post_json(self, url: str, *, json: Any = None, **kwargs: Any) -> Any:
        self._wait_rate_limit()
        resp = self._client.post(url, json=json, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def get_text(self, url: str, **kwargs: Any) -> str:
        self._wait_rate_limit()
        assert_safe_outbound_url(url)
        resp = self._client.get(url, **kwargs)
        resp.raise_for_status()
        return resp.text

    def _wait_rate_limit(self) -> None:
        if self._rate_limiter is not None:
            self._rate_limiter.wait()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
