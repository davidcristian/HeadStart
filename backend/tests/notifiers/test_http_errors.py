"""Unit tests for notifier HTTP error redaction."""

import httpx
import pytest

from app.notifiers.http_errors import safe_http_error


def test_safe_http_error_redacts_each_secret() -> None:
    url = "https://hooks.example/services/T00/B00/secret-token"
    request = httpx.Request("POST", url)
    response = httpx.Response(500, request=request)
    with pytest.raises(httpx.HTTPStatusError) as raised:
        response.raise_for_status()
    raw = str(raised.value)
    assert url in raw
    safe = safe_http_error(raised.value, url, "unused-topic")
    assert url not in safe
    assert "[REDACTED]" in safe
    assert "500" in safe


def test_safe_http_error_leaves_plain_text_when_no_secret_match() -> None:
    assert safe_http_error(ValueError("connection reset"), "https://secret") == "connection reset"
    assert safe_http_error(ValueError("plain"), "") == "plain"
    assert safe_http_error(ValueError("plain")) == "plain"
