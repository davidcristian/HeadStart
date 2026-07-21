"""Regression: compose db/redis bind loopback + require POSTGRES_PASSWORD."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_COMPOSE = _REPO_ROOT / "docker-compose.yml"
_ENV_EXAMPLE = _REPO_ROOT / ".env.example"
_DEPLOYMENT_DOC = _REPO_ROOT / "docs" / "modules" / "deployment.md"


def _compose_services() -> dict[str, Any]:
    """Load the root compose file and return its services map."""
    data = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
    services = data["services"]
    missing = {"db", "redis"} - services.keys()
    assert not missing, f"compose missing services: {sorted(missing)}"
    return services


def _published_ports(service: dict[str, Any]) -> list[str]:
    """Normalize a service ports list to strings for assertion."""
    ports = service.get("ports")
    assert isinstance(ports, list) and ports, "service must publish ports"
    return [str(p) for p in ports]


def test_db_and_redis_publish_on_loopback_only() -> None:
    """db/redis must bind 127.0.0.1 so LAN peers cannot reach them."""
    services = _compose_services()
    db_ports = _published_ports(services["db"])
    redis_ports = _published_ports(services["redis"])
    assert any(p.startswith("127.0.0.1:") and ":5432" in p for p in db_ports)
    assert any(p.startswith("127.0.0.1:") and ":6379" in p for p in redis_ports)
    assert not any(p.startswith("0.0.0.0:") for p in db_ports + redis_ports)
    # Bare HOST:CONTAINER without an explicit bind address defaults to 0.0.0.0.
    assert not any((":" in p and not p.startswith("127.0.0.1:")) for p in db_ports + redis_ports)


def test_compose_requires_explicit_postgres_password() -> None:
    """Compose must not default POSTGRES_PASSWORD to a weak literal."""
    text = _COMPOSE.read_text(encoding="utf-8")
    assert "POSTGRES_PASSWORD:-headstart" not in text
    assert "POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD" in text
    env_example = _ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "POSTGRES_PASSWORD=" in env_example


def test_deployment_doc_covers_compose_localhost_bind() -> None:
    """deployment.md must document the compose localhost-bind contract."""
    text = _DEPLOYMENT_DOC.read_text(encoding="utf-8")
    assert "127.0.0.1" in text
    assert "POSTGRES_PASSWORD" in text
