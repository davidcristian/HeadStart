"""Regression: Terraform S3 backend must not commit a CHANGEME bucket (OPS-29)."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TF_ENVS = _REPO_ROOT / "devops" / "terraform" / "environments"

_BACKEND_FILES = (
    _TF_ENVS / "beta" / "backend.tf",
    _TF_ENVS / "prod" / "backend.tf",
)

_EXAMPLE_FILES = (
    _TF_ENVS / "beta" / "backend.hcl.example",
    _TF_ENVS / "prod" / "backend.hcl.example",
)

_BUCKET_ASSIGNMENT = re.compile(r'^\s*bucket\s*=\s*"(?P<value>[^"]*)"', re.MULTILINE)


def test_backend_tf_omits_state_bucket() -> None:
    """Committed backend.tf must be a partial config with no bucket attribute."""
    for path in _BACKEND_FILES:
        text = path.read_text(encoding="utf-8")
        assert "CHANGEME" not in text, f"CHANGEME placeholder still in {path}"
        match = _BUCKET_ASSIGNMENT.search(text)
        assert match is None, f"committed bucket still present in {path}: {match.group(0)}"
        assert 'backend "s3"' in text
        assert "key" in text
        assert "encrypt" in text


def test_backend_hcl_example_documents_bucket_override() -> None:
    """Example backend.hcl must show how to supply the bootstrap bucket name."""
    for path in _EXAMPLE_FILES:
        text = path.read_text(encoding="utf-8")
        assert "CHANGEME" not in text, f"CHANGEME placeholder still in {path}"
        match = _BUCKET_ASSIGNMENT.search(text)
        assert match is not None, f"missing bucket assignment in {path}"
        assert "YOURNAME-headstart-tfstate" in match.group("value")


def test_bootstrap_script_does_not_instruct_editing_backend_tf() -> None:
    """Bootstrap next-steps must steer operators to -backend-config, not editing backend.tf."""
    script = (_REPO_ROOT / "scripts" / "terraform-bootstrap-state.sh").read_text(encoding="utf-8")
    assert "CHANGEME" not in script
    assert "-backend-config" in script
    assert "backend.hcl" in script
    assert "do not commit" in script.lower() or "OPS-29" in script
