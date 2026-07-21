"""Unit tests for Redis URL construction."""

from types import SimpleNamespace

from app.core.redis_url import build_redis_url, redis_url_from_settings


def test_plain_redis_url() -> None:
    assert build_redis_url(host="redis", port=6379, db=0) == "redis://redis:6379/0"


def test_tls_auth_percent_encodes_password() -> None:
    assert (
        build_redis_url(
            host="cache.example",
            port=6379,
            db=1,
            password="p@ss/word",
            tls=True,
        )
        == "rediss://:p%40ss%2Fword@cache.example:6379/1?ssl_cert_reqs=required"
    )


def test_password_without_tls() -> None:
    assert build_redis_url(host="r", port=6379, db=0, password="tok") == "redis://:tok@r:6379/0"


def test_redis_url_from_settings() -> None:
    settings = SimpleNamespace(
        redis_host="cache.example",
        redis_port=6379,
        redis_password="secret",
        redis_tls=True,
    )
    assert (
        redis_url_from_settings(settings, 0)
        == "rediss://:secret@cache.example:6379/0?ssl_cert_reqs=required"
    )
