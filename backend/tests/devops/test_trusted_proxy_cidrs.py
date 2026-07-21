"""Regression: ECS TRUSTED_PROXY_CIDRS must be the VPC CIDR."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_STACK_MAIN = _REPO_ROOT / "devops" / "terraform" / "modules" / "stack" / "main.tf"


def test_ecs_environment_sets_trusted_proxy_cidrs_to_vpc() -> None:
    """ALB peers live in the VPC; trust that CIDR for X-Forwarded-For."""
    text = _STACK_MAIN.read_text(encoding="utf-8")
    assert "TRUSTED_PROXY_CIDRS" in text
    assert "TRUSTED_PROXY_CIDRS              = var.vpc_cidr" in text
