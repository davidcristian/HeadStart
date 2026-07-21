"""Regression: compose api/worker/beat healthchecks + frontend gate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_COMPOSE = _REPO_ROOT / "docker-compose.yml"
_DEPLOYMENT_DOC = _REPO_ROOT / "docs" / "modules" / "deployment.md"


def _compose_services() -> dict[str, Any]:
    """Load the root compose file and return its services map."""
    data = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
    services = data["services"]
    missing = {"api", "worker", "beat", "frontend"} - services.keys()
    assert not missing, f"compose missing services: {sorted(missing)}"
    return services


def _healthcheck_command(service: dict[str, Any]) -> str:
    """Flatten a service healthcheck test to a single searchable string."""
    assert "healthcheck" in service, "service missing healthcheck"
    test = service["healthcheck"]["test"]
    if isinstance(test, list):
        return " ".join(str(part) for part in test)
    return str(test)


def test_api_worker_beat_define_healthchecks() -> None:
    """api/worker/beat must ship healthchecks (aligned with ECS probes)."""
    services = _compose_services()
    assert "/api/v1/health" in _healthcheck_command(services["api"])
    assert "/metrics" in _healthcheck_command(services["worker"])
    beat_cmd = _healthcheck_command(services["beat"])
    assert "/proc/" in beat_cmd and "beat" in beat_cmd


def test_frontend_waits_for_api_healthy() -> None:
    """frontend must not start until api reports healthy."""
    frontend = _compose_services()["frontend"]
    depends = frontend["depends_on"]
    assert isinstance(depends, dict), "frontend depends_on must use long form"
    assert depends["api"]["condition"] == "service_healthy"


def test_deployment_doc_covers_compose_healthchecks() -> None:
    """deployment.md must document the compose healthcheck contract."""
    text = _DEPLOYMENT_DOC.read_text(encoding="utf-8")
    assert "service_healthy" in text
    assert "/api/v1/health" in text
