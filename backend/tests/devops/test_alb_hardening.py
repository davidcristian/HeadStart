"""Regression: ALB Terraform hardens access logs, WAF, headers, deletion protection."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALB = _REPO_ROOT / "devops" / "terraform" / "modules" / "alb"
_STACK_VARS = _REPO_ROOT / "devops" / "terraform" / "modules" / "stack" / "variables.tf"
_STACK_MAIN = _REPO_ROOT / "devops" / "terraform" / "modules" / "stack" / "main.tf"
_PROD_MAIN = _REPO_ROOT / "devops" / "terraform" / "environments" / "prod" / "main.tf"


def test_alb_drops_invalid_headers_and_wires_access_logs() -> None:
    """Public ALB must drop malformed headers and ship access logs to S3."""
    main = (_ALB / "main.tf").read_text(encoding="utf-8")
    assert "drop_invalid_header_fields = true" in main
    assert "access_logs" in main
    assert "aws_s3_bucket.access_logs.id" in main
    assert "enable_deletion_protection = var.enable_deletion_protection" in main

    access_logs = (_ALB / "access_logs.tf").read_text(encoding="utf-8")
    assert 'resource "aws_s3_bucket" "access_logs"' in access_logs
    assert 'resource "aws_s3_bucket_policy" "access_logs"' in access_logs
    assert "aws_elb_service_account" in access_logs


def test_alb_associates_regional_wafv2_acl() -> None:
    """ALB must attach a regional WAFv2 ACL with AWS managed rule groups."""
    waf = (_ALB / "waf.tf").read_text(encoding="utf-8")
    assert 'resource "aws_wafv2_web_acl" "this"' in waf
    assert 'scope = "REGIONAL"' in waf
    assert "AWSManagedRulesCommonRuleSet" in waf
    assert "AWSManagedRulesKnownBadInputsRuleSet" in waf
    assert 'resource "aws_wafv2_web_acl_association" "this"' in waf
    assert "aws_lb.this.arn" in waf


def test_stack_plumbs_alb_deletion_protection_and_prod_enables_it() -> None:
    """Prod must opt into ALB deletion protection via the stack knob."""
    stack_vars = _STACK_VARS.read_text(encoding="utf-8")
    assert 'variable "alb_deletion_protection"' in stack_vars

    stack_main = _STACK_MAIN.read_text(encoding="utf-8")
    assert "enable_deletion_protection = var.alb_deletion_protection" in stack_main

    prod = _PROD_MAIN.read_text(encoding="utf-8")
    assert "alb_deletion_protection  = true" in prod or "alb_deletion_protection = true" in prod
