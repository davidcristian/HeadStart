"""Regression: ECS task defs pin non-root, readonly rootfs, and healthCheck."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ECS_MAIN = _REPO_ROOT / "devops" / "terraform" / "modules" / "ecs" / "main.tf"
_ENTRYPOINT = _REPO_ROOT / "backend" / "docker-entrypoint.sh"


def _ecs_text() -> str:
    return _ECS_MAIN.read_text(encoding="utf-8")


def test_ecs_pins_non_root_users() -> None:
    """Task defs must pin image UIDs so a rebuild cannot silently run as root."""
    text = _ecs_text()
    assert 'backend_user  = "10001:10001"' in text
    assert 'frontend_user = "101:101"' in text
    assert "user                   = local.backend_user" in text
    assert "user                   = local.frontend_user" in text


def test_ecs_enables_readonly_root_filesystem_with_tmpfs() -> None:
    """Long-running containers get readonlyRootFilesystem plus /tmp tmpfs scratch."""
    text = _ecs_text()
    assert "readonlyRootFilesystem = true" in text
    assert text.count("readonlyRootFilesystem = true") >= 2  # backend local + worker/frontend
    assert 'containerPath = "/tmp"' in text
    assert "tmpfs" in text


def test_long_running_containers_declare_health_checks() -> None:
    """api/worker/beat/frontend must declare container healthCheck; migrate may omit."""
    text = _ecs_text()
    assert "api_health_check" in text
    assert "worker_health_check" in text
    assert "beat_health_check" in text
    assert "frontend_health_check" in text
    assert "/api/v1/health" in text
    assert "127.0.0.1:9090/metrics" in text
    assert "127.0.0.1:8080/" in text
    # migrate is in the role loop but not in backend_health_by_role.
    assert "backend_health_by_role" in text
    assert re.search(r"api\s*=\s*local\.api_health_check", text)
    assert re.search(r"beat\s*=\s*local\.beat_health_check", text)
    assert "migrate" in text
    assert "One-off migrate" in text or "migrate has no long-lived probe" in text


def test_capability_drop_and_seccomp_apply_beyond_worker() -> None:
    """Drop-all + RuntimeDefault must apply to all roles via base_linux_parameters."""
    text = _ecs_text()
    assert "base_linux_parameters" in text
    assert 'drop = ["ALL"]' in text
    assert 'type = "RuntimeDefault"' in text
    assert "initProcessEnabled = true" in text


def test_beat_entrypoint_writes_schedule_under_tmp() -> None:
    """Beat must not write celerybeat-schedule onto a read-only /app."""
    entry = _ENTRYPOINT.read_text(encoding="utf-8")
    assert "--schedule=/tmp/celerybeat-schedule" in entry
