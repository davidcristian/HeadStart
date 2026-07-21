"""Regression: SPA HTML shell is not long-cached."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_NGINX_CONF = _REPO_ROOT / "frontend" / "nginx.conf"


def test_nginx_spa_location_sets_no_cache_on_html_shell() -> None:
    """index.html must revalidate so deploys do not leave stale asset hashes."""
    conf = _NGINX_CONF.read_text(encoding="utf-8")
    spa_block = conf.split("location / {", 1)[1].split("location ", 1)[0]
    assert 'add_header Cache-Control "no-cache"' in spa_block
    # Hashed bundles stay immutable; the shell must not inherit that policy.
    assert 'add_header Cache-Control "public, immutable"' not in spa_block
    assert "location /assets/" in conf
    assert 'add_header Cache-Control "public, immutable"' in conf
