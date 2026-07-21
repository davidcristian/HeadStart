"""Regression: ECS LOG_LEVEL is a Terraform variable, not a hardcoded INFO."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_STACK = _REPO_ROOT / "devops" / "terraform" / "modules" / "stack"
_BETA = _REPO_ROOT / "devops" / "terraform" / "environments" / "beta"
_PROD = _REPO_ROOT / "devops" / "terraform" / "environments" / "prod"


def test_stack_exposes_log_level_variable() -> None:
    """Stack must declare log_level with an INFO default and level validation."""
    variables = (_STACK / "variables.tf").read_text(encoding="utf-8")
    block = variables.split('variable "log_level"')[1].split("variable ")[0]
    assert 'default     = "INFO"' in block
    assert "upper(trimspace(var.log_level))" in block
    assert '"DEBUG"' in block
    assert '"CRITICAL"' in block


def test_ecs_environment_uses_log_level_variable() -> None:
    """ecs_environment must inject LOG_LEVEL from var.log_level, not a literal."""
    main = (_STACK / "main.tf").read_text(encoding="utf-8")
    assert "LOG_LEVEL     = upper(trimspace(var.log_level))" in main
    assert 'LOG_LEVEL     = "INFO"' not in main


def test_beta_and_prod_plumb_log_level() -> None:
    """Env wrappers must accept and forward log_level so tfvars can override."""
    for env in (_BETA, _PROD):
        variables = (env / "variables.tf").read_text(encoding="utf-8")
        assert 'variable "log_level"' in variables
        assert 'default     = "INFO"' in variables.split('variable "log_level"')[1]

        main = (env / "main.tf").read_text(encoding="utf-8")
        assert "log_level              = var.log_level" in main

        example = (env / "terraform.tfvars.example").read_text(encoding="utf-8")
        assert "log_level" in example
