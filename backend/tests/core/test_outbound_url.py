"""Tests for outbound URL safety policy."""

import pytest

from app.core.outbound_url import UnsafeOutboundUrlError, assert_safe_outbound_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/health",
        "http://localhost/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/",
        "http://192.168.1.1/",
        "file:///etc/passwd",
        "ftp://example.com/",
    ],
)
def test_assert_safe_outbound_url_rejects_unsafe_targets(url: str) -> None:
    with pytest.raises(UnsafeOutboundUrlError):
        assert_safe_outbound_url(url)


def test_assert_safe_outbound_url_allows_public_https() -> None:
    assert_safe_outbound_url("https://example.com/jobs")
