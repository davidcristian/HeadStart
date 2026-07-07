"""Build Celery Redis broker/result URLs (plain or TLS + AUTH)."""

from typing import Protocol
from urllib.parse import quote


class _RedisSettings(Protocol):
    redis_host: str
    redis_port: int
    redis_password: str
    redis_tls: bool


def build_redis_url(
    *,
    host: str,
    port: int,
    db: int,
    password: str = "",
    tls: bool = False,
) -> str:
    """Return redis:// or rediss:// URL; percent-encode AUTH when set (OPS-10)."""
    scheme = "rediss" if tls else "redis"
    auth = f":{quote(password, safe='')}@" if password else ""
    url = f"{scheme}://{auth}{host}:{port}/{db}"
    # Celery/kombu require ssl_cert_reqs on rediss://; ElastiCache uses public CAs.
    if tls:
        url = f"{url}?ssl_cert_reqs=required"
    return url


def redis_url_from_settings(settings: _RedisSettings, db: int) -> str:
    """Derive a Celery Redis URL from Settings-like redis_* fields."""
    return build_redis_url(
        host=settings.redis_host,
        port=settings.redis_port,
        db=db,
        password=settings.redis_password,
        tls=settings.redis_tls,
    )
