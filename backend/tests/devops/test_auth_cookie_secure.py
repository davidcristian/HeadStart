"""Regression: ECS AUTH_COOKIE_SECURE must follow ALB HTTPS."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_STACK_MAIN = _REPO_ROOT / "devops" / "terraform" / "modules" / "stack" / "main.tf"


def test_ecs_environment_derives_auth_cookie_secure_from_https() -> None:
    """HTTP ALB deploys must set AUTH_COOKIE_SECURE=false so refresh cookies stick."""
    text = _STACK_MAIN.read_text(encoding="utf-8")
    assert "AUTH_COOKIE_SECURE" in text
    assert 'AUTH_COOKIE_SECURE               = local.https_enabled ? "true" : "false"' in text
