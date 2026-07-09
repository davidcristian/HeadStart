"""Regression: production nginx ships SPA security headers (XCT-16)."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_NGINX_CONF = _REPO_ROOT / "frontend" / "nginx.conf"

# Headers the SPA HTML location must emit (defense-in-depth for the auth UI).
_REQUIRED_HEADERS = (
    "Content-Security-Policy",
    "X-Frame-Options",
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Strict-Transport-Security",
    "Permissions-Policy",
)


def test_nginx_spa_location_sets_security_headers() -> None:
    """The HTML shell must not ship without CSP / framing / HSTS hardening."""
    conf = _NGINX_CONF.read_text(encoding="utf-8")
    assert "listen 8080;" in conf
    assert "location / {" in conf
    for header in _REQUIRED_HEADERS:
        assert f"add_header {header}" in conf, f"missing add_header {header}"
    assert "frame-ancestors 'none'" in conf
    assert 'X-Frame-Options "DENY"' in conf
    assert "nosniff" in conf
    assert "max-age=31536000" in conf
    assert "always;" in conf


def test_nginx_asset_locations_repeat_nosniff() -> None:
    """Locations with their own add_header must restate nosniff (no inheritance)."""
    conf = _NGINX_CONF.read_text(encoding="utf-8")
    assert conf.count('add_header X-Content-Type-Options "nosniff" always;') >= 3
