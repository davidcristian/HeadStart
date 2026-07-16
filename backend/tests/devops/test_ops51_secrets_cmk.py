"""Regression: Secrets Manager uses a CMK and explicit recovery window (OPS-51)."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SECRETS = _REPO_ROOT / "devops" / "terraform" / "modules" / "secrets"
_IAM = _REPO_ROOT / "devops" / "terraform" / "modules" / "iam"
_STACK_MAIN = _REPO_ROOT / "devops" / "terraform" / "modules" / "stack" / "main.tf"


def test_secrets_provisions_cmk_with_key_rotation() -> None:
    """App secrets must encrypt with a customer-managed KMS key that rotates."""
    kms = (_SECRETS / "kms.tf").read_text(encoding="utf-8")
    assert 'resource "aws_kms_key" "secrets"' in kms
    assert "enable_key_rotation     = true" in kms
    assert "kms:ViaService" in kms
    assert "secretsmanager." in kms
    assert 'resource "aws_kms_alias" "secrets"' in kms


def test_secrets_use_cmk_and_explicit_recovery_window() -> None:
    """Each secret must pin the CMK and an explicit recovery_window_in_days."""
    main = (_SECRETS / "main.tf").read_text(encoding="utf-8")
    assert "kms_key_id              = aws_kms_key.secrets.arn" in main
    assert "recovery_window_in_days = var.recovery_window_in_days" in main

    variables = (_SECRETS / "variables.tf").read_text(encoding="utf-8")
    recovery_block = variables.split('variable "recovery_window_in_days"')[1].split("variable ")[0]
    assert "default     = 30" in recovery_block


def test_ecs_execution_role_may_decrypt_secrets_cmk() -> None:
    """Execution role must Decrypt the secrets CMK when fetching secret values."""
    iam_main = (_IAM / "main.tf").read_text(encoding="utf-8")
    assert 'actions   = ["kms:Decrypt", "kms:DescribeKey"]' in iam_main
    assert "var.secrets_kms_key_arn" in iam_main

    stack = _STACK_MAIN.read_text(encoding="utf-8")
    assert "secrets_kms_key_arn  = module.secrets.kms_key_arn" in stack
    assert 'output "kms_key_arn"' in (_SECRETS / "outputs.tf").read_text(encoding="utf-8")
