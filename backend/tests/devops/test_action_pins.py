"""Regression: third-party GitHub Actions stay SHA-pinned."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WORKFLOWS = _REPO_ROOT / ".github" / "workflows"
_DEPENDABOT = _REPO_ROOT / ".github" / "dependabot.yml"

# Full 40-char SHAs are required, not mutable major/minor tags (e.g. @v4, @v5.6).
_FLOATING_USES = re.compile(r"(?m)^\s*-?\s*uses:\s*[^\s#]+@v\d[\w.]*\s*(?:#.*)?$")
_SHA_USES = re.compile(r"(?m)^\s*-?\s*uses:\s*[^\s@]+@[0-9a-f]{40}\s*(?:#.*)?$")


def _workflow_texts() -> dict[str, str]:
    """Load every workflow YAML under .github/workflows/."""
    paths = sorted(_WORKFLOWS.glob("*.yml"))
    return {path.name: path.read_text(encoding="utf-8") for path in paths}


def test_no_floating_action_version_tags() -> None:
    """uses: must not reference mutable @vN tags (supply-chain pin)."""
    for name, text in _workflow_texts().items():
        floating = _FLOATING_USES.findall(text)
        assert floating == [], f"{name} still has floating action tags: {floating}"


def test_every_uses_is_full_commit_sha() -> None:
    """Every third-party uses: line must pin a 40-char commit SHA."""
    for name, text in _workflow_texts().items():
        uses_lines = [line for line in text.splitlines() if re.match(r"^\s*-?\s*uses:\s*", line)]
        assert uses_lines, f"{name} has no uses: steps"
        for line in uses_lines:
            assert _SHA_USES.match(line), f"{name}: not SHA-pinned: {line!r}"


def test_dependabot_watches_github_actions() -> None:
    """Dependabot must open weekly PRs that bump action SHAs."""
    text = _DEPENDABOT.read_text(encoding="utf-8")
    assert "package-ecosystem: github-actions" in text
    assert "directory: /" in text
