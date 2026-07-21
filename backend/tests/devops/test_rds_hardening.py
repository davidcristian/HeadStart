"""Regression: RDS Terraform hardens encryption, auth, and observability."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RDS = _REPO_ROOT / "devops" / "terraform" / "modules" / "rds"


def test_rds_provisions_cmk_with_key_rotation() -> None:
    """RDS must encrypt with a customer-managed KMS key that rotates annually."""
    kms = (_RDS / "kms.tf").read_text(encoding="utf-8")
    assert 'resource "aws_kms_key" "rds"' in kms
    assert "enable_key_rotation     = true" in kms
    assert "rds.amazonaws.com" in kms
    assert 'resource "aws_kms_alias" "rds"' in kms


def test_rds_enables_iam_auth_pi_logs_and_monitoring() -> None:
    """Instance must enable IAM auth, PI, Postgres log exports, and EM."""
    main = (_RDS / "main.tf").read_text(encoding="utf-8")
    assert "kms_key_id            = aws_kms_key.rds.arn" in main
    assert "iam_database_authentication_enabled = true" in main
    assert "performance_insights_enabled          = true" in main
    assert "performance_insights_kms_key_id       = aws_kms_key.rds.arn" in main
    assert 'enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]' in main
    assert "monitoring_interval = var.monitoring_interval" in main
    assert "aws_iam_role.monitoring.arn" in main
    assert "var.monitoring_interval > 0" in main
    assert "apply_immediately         = var.apply_immediately" in main

    monitoring = (_RDS / "monitoring.tf").read_text(encoding="utf-8")
    assert 'resource "aws_iam_role" "monitoring"' in monitoring
    assert "monitoring.rds.amazonaws.com" in monitoring
    assert "AmazonRDSEnhancedMonitoringRole" in monitoring


def test_rds_apply_immediately_defaults_false() -> None:
    """Disruptive apply_immediately must default off (maintenance window)."""
    variables = (_RDS / "variables.tf").read_text(encoding="utf-8")
    assert 'variable "apply_immediately"' in variables
    # Default block sits on the line after the type declaration.
    apply_block = variables.split('variable "apply_immediately"')[1].split("variable ")[0]
    assert "default     = false" in apply_block
    assert 'variable "monitoring_interval"' in variables
    assert (
        "default     = 60"
        in variables.split('variable "monitoring_interval"')[1].split("variable ")[0]
    )
