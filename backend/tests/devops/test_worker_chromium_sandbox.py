"""Regression: worker ECS task hardens Chromium with RuntimeDefault seccomp."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ECS_MAIN = _REPO_ROOT / "devops" / "terraform" / "modules" / "ecs" / "main.tf"


def test_worker_container_uses_runtime_default_seccomp() -> None:
    """Worker task def must pin RuntimeDefault seccomp and drop all capabilities."""
    text = _ECS_MAIN.read_text(encoding="utf-8")
    # Shared with other roles; worker must still consume it.
    assert "base_linux_parameters" in text
    assert 'type = "RuntimeDefault"' in text
    assert "seccompProfile" in text
    assert 'drop = ["ALL"]' in text
    assert "initProcessEnabled = true" in text
    start = text.index("worker_container = jsonencode")
    end = text.index("])", start)
    worker = text[start:end]
    assert "local.base_linux_parameters" in worker


def test_dockerfile_documents_chromium_sandbox_posture() -> None:
    """Worker image comments must state Chromium keeps its process sandbox."""
    dockerfile = (_REPO_ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    assert "process sandbox" in dockerfile.lower() or "Chromium's process sandbox" in dockerfile
    assert "--no-sandbox" in dockerfile  # documented as forbidden in production
