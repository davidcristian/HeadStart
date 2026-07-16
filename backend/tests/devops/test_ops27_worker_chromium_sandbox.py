"""Regression: worker ECS task hardens Chromium with RuntimeDefault seccomp (OPS-27)."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ECS_MAIN = _REPO_ROOT / "devops" / "terraform" / "modules" / "ecs" / "main.tf"


def test_worker_container_uses_runtime_default_seccomp() -> None:
    """Worker task def must pin RuntimeDefault seccomp and drop all capabilities."""
    text = _ECS_MAIN.read_text(encoding="utf-8")
    # Scope to the worker_container local only.
    start = text.index("worker_container = jsonencode")
    end = text.index("])", start)
    worker = text[start:end]
    assert "OPS-27" in worker or "OPS-27" in text[start - 120 : start]
    assert 'type = "RuntimeDefault"' in worker
    assert "seccompProfile" in worker
    assert 'drop = ["ALL"]' in worker
    assert "initProcessEnabled = true" in worker


def test_dockerfile_documents_chromium_sandbox_posture() -> None:
    """Worker image comments must state Chromium keeps its process sandbox."""
    dockerfile = (_REPO_ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    assert "OPS-27" in dockerfile
    assert "process sandbox" in dockerfile.lower() or "Chromium's process sandbox" in dockerfile
    assert "--no-sandbox" in dockerfile  # documented as forbidden in production
