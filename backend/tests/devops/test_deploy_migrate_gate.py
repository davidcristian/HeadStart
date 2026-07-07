"""Regression: deploy must await migrate success before rolling ECS (OPS-17)."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEPLOY_SH = _REPO_ROOT / "scripts" / "deploy.sh"


def test_deploy_awaits_migrate_before_service_roll() -> None:
    """Fire-and-forget migrate must not precede unconditional update-service."""
    text = _DEPLOY_SH.read_text(encoding="utf-8")
    assert "run_and_await_migrate_task" in text
    assert "aws ecs wait tasks-stopped" in text
    assert "containers[*].exitCode" in text
    assert "aborting service roll" in text
    assert '|| warn "migrate task submission failed' not in text
    await_pos = text.index("run_and_await_migrate_task")
    roll_pos = text.index("aws ecs update-service")
    assert await_pos < roll_pos, "migrate await must run before service roll"


def test_deploy_migrate_helper_dies_on_nonzero_exit() -> None:
    """Non-zero container exit codes must abort via die, not warn."""
    text = _DEPLOY_SH.read_text(encoding="utf-8")
    start = text.index("run_and_await_migrate_task()")
    end = text.index('\nlog "Deploying tag', start)
    helper = text[start:end]
    assert 'die "migrate task failed' in helper
    assert "warn" not in helper
