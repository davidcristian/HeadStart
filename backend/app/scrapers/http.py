"""Small synchronous HTTP helper shared by scrapers.

Centralizes the User-Agent, timeouts, and redirect policy so individual
adapters stay focused on parsing.
"""

from typing import Any

import httpx

DEFAULT_USER_AGENT = "JobNotifier/0.1 (+https://github.com/; polite job-posting watcher)"
DEFAULT_TIMEOUT = 20.0


class HttpClient:
    def __init__(
        self,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = DEFAULT_TIMEOUT,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._owns_client = client is None
        merged_headers = {"User-Agent": user_agent, **(headers or {})}
        self._client = client or httpx.Client(
            headers=merged_headers,
            cookies=cookies or {},
            timeout=timeout,
            follow_redirects=True,
        )

    def get_json(self, url: str, **kwargs: Any) -> Any:
        resp = self._client.get(url, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def get_text(self, url: str, **kwargs: Any) -> str:
        resp = self._client.get(url, **kwargs)
        resp.raise_for_status()
        return resp.text

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
