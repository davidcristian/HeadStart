"""Regression: prod Terraform must not default ECS images to mutable latest (OPS-07)."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PROD_VARS = _REPO_ROOT / "devops" / "terraform" / "environments" / "prod" / "variables.tf"
_PROD_TFVARS = (
    _REPO_ROOT / "devops" / "terraform" / "environments" / "prod" / "terraform.tfvars.example"
)

_IMAGE_TAG_BLOCK = re.compile(
    r'variable\s+"image_tag"\s*\{(?P<body>.*?)\n\}',
    re.DOTALL,
)


def test_prod_image_tag_requires_immutable_pin() -> None:
    """Prod must require an explicit tag and reject the floating latest default."""
    text = _PROD_VARS.read_text(encoding="utf-8")
    match = _IMAGE_TAG_BLOCK.search(text)
    assert match is not None, "missing image_tag in prod variables.tf"
    body = match.group("body")
    assert not re.search(
        r"^\s*default\s*=", body, re.MULTILINE
    ), "prod image_tag still has a default"
    assert "validation" in body, "missing validation block for prod image_tag"
    assert 'lower(trimspace(var.image_tag)) != "latest"' in body
    assert "length(trimspace(var.image_tag)) > 0" in body


def test_prod_tfvars_example_does_not_pin_latest() -> None:
    """Example tfvars must not bake in the mutable latest tag."""
    text = _PROD_TFVARS.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("image_tag") and not stripped.startswith("#"):
            assert (
                "latest" not in stripped.lower()
            ), f"mutable latest still in {_PROD_TFVARS}: {line}"
            return
    raise AssertionError(f"missing active image_tag assignment in {_PROD_TFVARS}")
