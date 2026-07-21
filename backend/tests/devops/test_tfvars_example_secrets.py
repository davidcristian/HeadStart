"""Regression: tfvars.example must not prime inline core secrets."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TF_ENVS = _REPO_ROOT / "devops" / "terraform" / "environments"

# These three are required at apply time and historically appeared as active
# change-me assignments in terraform.tfvars.example, priming operators to paste
# real secrets into a file. smtp_password was already env-var-only.
_CORE_SECRETS = ("db_password", "jwt_secret", "credentials_secret_key")


def test_tfvars_examples_require_core_secrets_via_tf_var_only() -> None:
    """Beta/prod examples must document TF_VAR_* and never assign core secrets."""
    for env in ("beta", "prod"):
        path = _TF_ENVS / env / "terraform.tfvars.example"
        text = path.read_text(encoding="utf-8")
        for name in _CORE_SECRETS:
            assert f"TF_VAR_{name}" in text, f"{path} missing TF_VAR_{name} guidance"
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if stripped.startswith(f"{name}") and "=" in stripped:
                    raise AssertionError(f"active {name} assignment in {path}: {line}")
