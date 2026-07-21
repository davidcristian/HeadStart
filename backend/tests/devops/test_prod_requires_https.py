"""Regression: prod Terraform must require ALB HTTPS."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_STACK_MAIN = _REPO_ROOT / "devops" / "terraform" / "modules" / "stack" / "main.tf"
_PROD_VARS = _REPO_ROOT / "devops" / "terraform" / "environments" / "prod" / "variables.tf"
_PROD_TFVARS = (
    _REPO_ROOT / "devops" / "terraform" / "environments" / "prod" / "terraform.tfvars.example"
)
_DEPLOYMENT_DOC = _REPO_ROOT / "docs" / "modules" / "deployment.md"


def test_stack_check_requires_https_for_prod() -> None:
    """Prod must fail plan/apply when the ALB would forward plaintext HTTP."""
    text = _STACK_MAIN.read_text(encoding="utf-8")
    assert 'check "prod_requires_https"' in text
    assert 'var.environment != "prod" || local.https_enabled' in text


def test_prod_variables_document_https_requirement() -> None:
    """Prod variables must declare the domain, zone and certificate HTTPS inputs."""
    text = _PROD_VARS.read_text(encoding="utf-8")
    assert "domain_name" in text
    assert "route53_zone_id" in text
    assert "acm_certificate_arn" in text


def test_prod_tfvars_example_requires_https_inputs() -> None:
    """Example tfvars must show active domain/zone pins for prod HTTPS."""
    text = _PROD_TFVARS.read_text(encoding="utf-8")
    has_domain = False
    has_zone = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped.startswith("domain_name"):
            has_domain = True
            assert '""' not in stripped, f"empty domain_name in example: {line}"
        if stripped.startswith("route53_zone_id"):
            has_zone = True
            assert '""' not in stripped, f"empty route53_zone_id in example: {line}"
    assert has_domain, f"missing active domain_name in {_PROD_TFVARS}"
    assert has_zone, f"missing active route53_zone_id in {_PROD_TFVARS}"


def test_deployment_doc_states_prod_requires_https() -> None:
    """deployment.md must document that prod refuses plaintext ALB forwarding."""
    text = _DEPLOYMENT_DOC.read_text(encoding="utf-8")
    assert "prod" in text.lower() and "https" in text.lower()
