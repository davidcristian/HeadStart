"""Regression: Terraform must inject METRICS_TOKEN into ECS (OPS-54)."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_STACK_MAIN = _REPO_ROOT / "devops" / "terraform" / "modules" / "stack" / "main.tf"


def test_stack_generates_and_injects_metrics_token() -> None:
    """ECS tasks must receive METRICS_TOKEN from Secrets Manager, not leave it empty."""
    text = _STACK_MAIN.read_text(encoding="utf-8")
    assert 'resource "random_password" "metrics_token"' in text
    assert "METRICS_TOKEN          = random_password.metrics_token.result" in text
    assert 'METRICS_TOKEN          = module.secrets.secret_arns["METRICS_TOKEN"]' in text
