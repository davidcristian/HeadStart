"""Regression: terraform credentialed plan never runs on PR checkouts."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TF_YML = _REPO_ROOT / ".github" / "workflows" / "terraform.yml"


def _tf_text() -> str:
    """Load the terraform workflow YAML."""
    return _TF_YML.read_text(encoding="utf-8")


def _job_blocks(text: str) -> dict[str, str]:
    """Split top-level job bodies keyed by job id (best-effort for tests)."""
    jobs_match = re.search(r"(?m)^jobs:\n([\s\S]*)", text)
    assert jobs_match is not None, "terraform.yml missing jobs:"
    body = jobs_match.group(1)
    parts = re.split(r"(?m)^(  [a-zA-Z0-9_-]+:)\n", body)
    # parts: [preamble, '  validate:', validate_body, '  plan:', plan_body, ...]
    out: dict[str, str] = {}
    i = 1
    while i + 1 < len(parts):
        key = parts[i].strip().rstrip(":")
        out[key] = parts[i + 1]
        i += 2
    return out


def test_validate_job_has_no_tf_secrets_or_aws_oidc() -> None:
    """PR validate path must not inject TF_VAR secrets or assume AWS."""
    jobs = _job_blocks(_tf_text())
    assert "validate" in jobs
    validate = jobs["validate"]
    assert "TF_VAR_" not in validate
    assert "secrets.TF_VAR_" not in validate
    assert "configure-aws-credentials" not in validate
    assert "AWS_ROLE_ARN" not in validate


def test_plan_job_refuses_pull_request_and_requires_default_branch() -> None:
    """Credentialed plan must be workflow_dispatch on main/master only."""
    jobs = _job_blocks(_tf_text())
    assert "plan" in jobs
    plan = jobs["plan"]
    match = re.search(r"(?m)^\s+if:\s*\$\{\{(.+?)\}\}\s*$", plan)
    assert match is not None, "plan job is missing an if: guard"
    cond = match.group(1)
    assert "AWS_ROLE_ARN" in cond
    assert "workflow_dispatch" in cond
    assert "refs/heads/master" in cond
    assert "refs/heads/main" in cond
    assert "pull_request" not in cond


def test_plan_job_uses_environment_and_oidc_session() -> None:
    """Plan must target a GitHub Environment and set OIDC audience/session."""
    jobs = _job_blocks(_tf_text())
    plan = jobs["plan"]
    assert "environment:" in plan
    assert "audience: sts.amazonaws.com" in plan
    assert "role-session-name: headstart-tf-plan-${{ github.run_id }}" in plan
    assert "configure-aws-credentials" in plan
    # Secrets belong only on the trusted plan job.
    assert "secrets.TF_VAR_DB_PASSWORD" in plan
    assert "secrets.TF_VAR_JWT_SECRET" in plan
    assert "secrets.TF_VAR_CREDENTIALS_SECRET_KEY" in plan


def test_workflow_documents_ops24_no_pr_secrets() -> None:
    """Header must document that PR checkouts never get TF secrets / AWS."""
    text = _tf_text()
    assert "pull_request" in text.lower()
    assert "untrusted" in text.lower() or "Never inject" in text
    assert "TF_STATE_BUCKET" in text
