"""Regression: RDS final snapshot is independent of deletion_protection."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RDS = _REPO_ROOT / "devops" / "terraform" / "modules" / "rds"
_STACK_MAIN = _REPO_ROOT / "devops" / "terraform" / "modules" / "stack" / "main.tf"
_STACK_VARS = _REPO_ROOT / "devops" / "terraform" / "modules" / "stack" / "variables.tf"
_BETA_MAIN = _REPO_ROOT / "devops" / "terraform" / "environments" / "beta" / "main.tf"
_PROD_MAIN = _REPO_ROOT / "devops" / "terraform" / "environments" / "prod" / "main.tf"
_DEPLOYMENT_DOC = _REPO_ROOT / "docs" / "modules" / "deployment.md"


def test_rds_skip_final_snapshot_is_independent_of_deletion_protection() -> None:
    """Destroy snapshot must not be coupled to deletion_protection."""
    main = (_RDS / "main.tf").read_text(encoding="utf-8")
    assert "skip_final_snapshot       = var.skip_final_snapshot" in main
    assert "final_snapshot_identifier = var.skip_final_snapshot ? null" in main
    assert '"${var.name}-final"' in main
    assert "skip_final_snapshot     = !var.deletion_protection" not in main

    variables = (_RDS / "variables.tf").read_text(encoding="utf-8")
    assert 'variable "skip_final_snapshot"' in variables
    skip_block = variables.split('variable "skip_final_snapshot"')[1].split("variable ")[0]
    assert "default     = false" in skip_block


def test_stack_check_requires_prod_rds_destroy_safety() -> None:
    """Prod must fail plan/apply without deletion protection and a final snapshot."""
    text = _STACK_MAIN.read_text(encoding="utf-8")
    assert 'check "prod_requires_db_deletion_protection"' in text
    assert "var.db_deletion_protection && !var.db_skip_final_snapshot" in text
    assert "skip_final_snapshot   = var.db_skip_final_snapshot" in text

    stack_vars = _STACK_VARS.read_text(encoding="utf-8")
    assert 'variable "db_skip_final_snapshot"' in stack_vars
    skip_block = stack_vars.split('variable "db_skip_final_snapshot"')[1].split("variable ")[0]
    assert "default     = false" in skip_block


def test_beta_opts_into_skip_final_snapshot_prod_keeps_protection() -> None:
    """Beta may skip the snapshot for throwaway teardown; prod must not."""
    beta = _BETA_MAIN.read_text(encoding="utf-8")
    assert "db_skip_final_snapshot   = true" in beta
    assert "db_deletion_protection   = false" in beta

    prod = _PROD_MAIN.read_text(encoding="utf-8")
    assert "db_deletion_protection   = true" in prod
    assert "db_skip_final_snapshot" not in prod


def test_deployment_doc_states_ops48_rds_destroy_safety() -> None:
    """deployment.md must document the decoupled snapshot knob and prod check."""
    text = _DEPLOYMENT_DOC.read_text(encoding="utf-8")
    assert "prod_requires_db_deletion_protection" in text
    assert "db_skip_final_snapshot" in text
