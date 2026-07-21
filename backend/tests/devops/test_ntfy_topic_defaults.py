"""Regression: Terraform must not default ntfy topics to a public placeholder."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TF_ROOT = _REPO_ROOT / "devops" / "terraform"

_VARIABLE_FILES = (
    _TF_ROOT / "modules" / "stack" / "variables.tf",
    _TF_ROOT / "environments" / "prod" / "variables.tf",
    _TF_ROOT / "environments" / "beta" / "variables.tf",
)

_TFVARS_EXAMPLES = (
    _TF_ROOT / "environments" / "prod" / "terraform.tfvars.example",
    _TF_ROOT / "environments" / "beta" / "terraform.tfvars.example",
)

_PLACEHOLDER = "headstart-change-me"
_TOPIC_BLOCK = re.compile(
    r'variable\s+"ntfy_default_topic"\s*\{(?P<body>.*?)\n\}',
    re.DOTALL,
)


def test_ntfy_default_topic_has_no_insecure_default() -> None:
    """Stack and env modules must require an explicit unguessable topic."""
    for path in _VARIABLE_FILES:
        text = path.read_text(encoding="utf-8")
        match = _TOPIC_BLOCK.search(text)
        assert match is not None, f"missing ntfy_default_topic in {path}"
        body = match.group("body")
        assert not re.search(
            r"^\s*default\s*=", body, re.MULTILINE
        ), f"insecure default still present in {path}"
        assert "validation" in body, f"missing validation block in {path}"
        assert 'strcontains(lower(var.ntfy_default_topic), "change-me")' in body
        assert _PLACEHOLDER not in body


def test_tfvars_examples_do_not_assign_placeholder_topic() -> None:
    """Example tfvars must not bake in the public headstart-change-me topic."""
    for path in _TFVARS_EXAMPLES:
        text = path.read_text(encoding="utf-8")
        assert _PLACEHOLDER not in text, f"placeholder still in {path}"
        # Active assignment would let operators copy a static topic; keep it commented.
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("ntfy_default_topic"):
                raise AssertionError(f"active ntfy_default_topic assignment in {path}: {line}")
