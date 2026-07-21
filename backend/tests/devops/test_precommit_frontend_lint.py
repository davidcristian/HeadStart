"""Regression: pre-commit frontend eslint must pass a path."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PRECOMMIT = _REPO_ROOT / ".pre-commit-config.yaml"


def test_frontend_lint_hook_passes_eslint_path() -> None:
    """ESLint with no path lints zero files; the hook must invoke `eslint .`."""
    text = _PRECOMMIT.read_text(encoding="utf-8")
    assert "id: frontend-lint" in text
    assert "npx eslint . --max-warnings=0" in text
    assert "frontend eslint (changed files)" not in text
