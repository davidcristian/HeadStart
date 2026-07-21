"""Regression: deploy OIDC assumes a scoped role with audit session."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEPLOY_YML = _REPO_ROOT / ".github" / "workflows" / "deploy.yml"


def _deploy_text() -> str:
    """Load the deploy workflow YAML."""
    return _DEPLOY_YML.read_text(encoding="utf-8")


def test_deploy_job_requires_default_branch_ref() -> None:
    """Job if must refuse non-main/master refs even when AWS_ROLE_ARN is set."""
    text = _deploy_text()
    assert "vars.AWS_ROLE_ARN != ''" in text
    assert "github.ref == 'refs/heads/master'" in text
    assert "github.ref == 'refs/heads/main'" in text
    # Both conditions must appear in the same job-level if expression.
    match = re.search(r"(?m)^\s+if:\s*\$\{\{(.+?)\}\}\s*$", text)
    assert match is not None, "deploy job is missing an if: guard"
    cond = match.group(1)
    assert "AWS_ROLE_ARN" in cond
    assert "refs/heads/master" in cond
    assert "refs/heads/main" in cond


def test_configure_aws_credentials_sets_audience_and_session_name() -> None:
    """OIDC step must set audience + role-session-name for aud/sub + CloudTrail."""
    text = _deploy_text()
    assert "audience: sts.amazonaws.com" in text
    assert "role-session-name: headstart-deploy-${{ github.run_id }}" in text


def test_deploy_documents_iam_trust_policy_sub_pinning() -> None:
    """Workflow header must document required IAM trust-policy sub scoping."""
    text = _deploy_text()
    assert "token.actions.githubusercontent.com:sub" in text
    assert "repo:OWNER/REPO:*" in text or "wildcard" in text.lower()
    assert "Settings → Environments" in text or "required reviewers" in text
