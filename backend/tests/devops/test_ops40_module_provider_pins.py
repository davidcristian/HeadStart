"""Regression: reusable Terraform modules pin required_providers (OPS-40)."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MODULES = _REPO_ROOT / "devops" / "terraform" / "modules"

_AWS_BLOCK = re.compile(
    r'aws\s*=\s*\{[^}]*source\s*=\s*"hashicorp/aws"[^}]*version\s*=\s*">=\s*5\.60"[^}]*\}',
    re.DOTALL,
)
_RANDOM_BLOCK = re.compile(
    r'random\s*=\s*\{[^}]*source\s*=\s*"hashicorp/random"[^}]*version\s*=\s*">=\s*3\.6"[^}]*\}',
    re.DOTALL,
)
_TF_VERSION = re.compile(r'required_version\s*=\s*">=\s*1\.5\.0"')


def test_every_module_declares_versions_tf() -> None:
    """Each reusable module must ship versions.tf so callers cannot omit a pin."""
    module_dirs = sorted(p for p in _MODULES.iterdir() if p.is_dir())
    assert module_dirs, "expected terraform modules under devops/terraform/modules"
    for module_dir in module_dirs:
        versions = module_dir / "versions.tf"
        assert versions.is_file(), f"{module_dir.name} missing versions.tf (OPS-40)"


def test_module_versions_pin_aws_provider_floor() -> None:
    """Modules must require hashicorp/aws >= 5.60 (matching env root floors)."""
    for module_dir in sorted(p for p in _MODULES.iterdir() if p.is_dir()):
        text = (module_dir / "versions.tf").read_text(encoding="utf-8")
        assert _TF_VERSION.search(text), f"{module_dir.name} missing terraform >= 1.5.0"
        assert "required_providers" in text, f"{module_dir.name} missing required_providers"
        assert _AWS_BLOCK.search(text), f"{module_dir.name} missing aws >= 5.60 pin (OPS-40)"


def test_stack_module_also_pins_random_provider() -> None:
    """stack uses random_password; it must declare the random provider floor."""
    text = (_MODULES / "stack" / "versions.tf").read_text(encoding="utf-8")
    assert _RANDOM_BLOCK.search(text), "stack versions.tf missing random >= 3.6 (OPS-40)"
