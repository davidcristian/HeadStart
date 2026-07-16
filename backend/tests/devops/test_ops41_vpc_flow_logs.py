"""Regression: VPC Terraform enables CloudWatch flow logs (OPS-41)."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_NETWORK = _REPO_ROOT / "devops" / "terraform" / "modules" / "network"
_STACK_MAIN = _REPO_ROOT / "devops" / "terraform" / "modules" / "stack" / "main.tf"
_STACK_VARS = _REPO_ROOT / "devops" / "terraform" / "modules" / "stack" / "variables.tf"
_PROD_MAIN = _REPO_ROOT / "devops" / "terraform" / "environments" / "prod" / "main.tf"


def test_network_enables_vpc_flow_logs_to_cloudwatch() -> None:
    """VPC must publish ALL traffic flow logs to a retained CloudWatch group."""
    flow_logs = (_NETWORK / "flow_logs.tf").read_text(encoding="utf-8")
    assert 'resource "aws_flow_log" "this"' in flow_logs
    assert 'traffic_type    = "ALL"' in flow_logs
    assert "vpc_id          = aws_vpc.this.id" in flow_logs
    assert 'resource "aws_cloudwatch_log_group" "flow_log"' in flow_logs
    assert "retention_in_days = var.flow_log_retention_days" in flow_logs
    assert 'resource "aws_iam_role" "flow_log"' in flow_logs
    assert "vpc-flow-logs.amazonaws.com" in flow_logs

    variables = (_NETWORK / "variables.tf").read_text(encoding="utf-8")
    assert 'variable "flow_log_retention_days"' in variables

    outputs = (_NETWORK / "outputs.tf").read_text(encoding="utf-8")
    assert 'output "flow_log_group_name"' in outputs


def test_stack_plumbs_log_retention_into_vpc_flow_logs() -> None:
    """Stack must reuse log_retention_days for VPC flow log CloudWatch retention."""
    stack_main = _STACK_MAIN.read_text(encoding="utf-8")
    assert "flow_log_retention_days  = var.log_retention_days" in stack_main

    stack_vars = _STACK_VARS.read_text(encoding="utf-8")
    assert "VPC flow logs" in stack_vars

    prod = _PROD_MAIN.read_text(encoding="utf-8")
    assert "log_retention_days" in prod
    assert "90" in prod
