"""Regression: beta/prod AWS providers must pin allowed_account_ids (OPS-31)."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TF_ENVS = _REPO_ROOT / "devops" / "terraform" / "environments"
_FIRST_DEPLOY = _REPO_ROOT / "scripts" / "aws-first-deploy.sh"

_ACCOUNT_BLOCK = re.compile(
    r'variable\s+"aws_account_id"\s*\{(?P<body>.*?)\n\}',
    re.DOTALL,
)
_ALLOWED = re.compile(
    r"allowed_account_ids\s*=\s*\[\s*var\.aws_account_id\s*\]",
)


def test_env_providers_pin_allowed_account_ids() -> None:
    """Beta and prod providers must refuse credentials outside aws_account_id."""
    for env in ("beta", "prod"):
        text = (_TF_ENVS / env / "providers.tf").read_text(encoding="utf-8")
        assert _ALLOWED.search(text), f"{env} providers.tf missing allowed_account_ids (OPS-31)"


def test_env_aws_account_id_is_required_and_validated() -> None:
    """aws_account_id must have no default and reject non-12-digit values."""
    for env in ("beta", "prod"):
        text = (_TF_ENVS / env / "variables.tf").read_text(encoding="utf-8")
        match = _ACCOUNT_BLOCK.search(text)
        assert match is not None, f"missing aws_account_id in {env}/variables.tf"
        body = match.group("body")
        assert not re.search(
            r"^\s*default\s*=", body, re.MULTILINE
        ), f"{env} aws_account_id still has a default"
        assert "validation" in body, f"missing validation block in {env}/variables.tf"
        assert 'regex("^[0-9]{12}$", var.aws_account_id)' in body


def test_tfvars_examples_do_not_bake_in_account_id() -> None:
    """Example tfvars must not ship an active aws_account_id assignment."""
    for env in ("beta", "prod"):
        path = _TF_ENVS / env / "terraform.tfvars.example"
        text = path.read_text(encoding="utf-8")
        assert "OPS-31" in text, f"{path} should document the account pin"
        assert "TF_VAR_aws_account_id" in text
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("aws_account_id"):
                raise AssertionError(f"active aws_account_id assignment in {path}: {line}")


def test_aws_first_deploy_resolves_account_id() -> None:
    """First-deploy must set or validate TF_VAR_aws_account_id before apply."""
    text = _FIRST_DEPLOY.read_text(encoding="utf-8")
    assert "TF_VAR_aws_account_id" in text
    assert "get-caller-identity" in text
    assert "OPS-31" in text
    assert "export TF_VAR_aws_account_id=" in text
