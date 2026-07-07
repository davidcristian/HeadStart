"""Regression: LOC, shell, and prettier gates stay wired (OPS-04)."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PRECOMMIT = _REPO_ROOT / ".pre-commit-config.yaml"
_LINT_SH = _REPO_ROOT / "scripts" / "lint.sh"
_CI_YML = _REPO_ROOT / ".github" / "workflows" / "ci.yml"


def test_precommit_header_is_fast_subset_not_full_mirror() -> None:
    """Pre-commit must not claim to mirror the full CI gate (OPS-04 / OPS-25)."""
    text = _PRECOMMIT.read_text(encoding="utf-8")
    assert "mirror the CI quality gate" not in text.lower()
    assert "fast local subset" in text.lower() or "fast subset" in text.lower()


def test_precommit_runs_loc_shell_and_prettier() -> None:
    """Commit-time hooks must enforce the three gates CI also covers."""
    text = _PRECOMMIT.read_text(encoding="utf-8")
    assert "id: check-loc" in text
    assert "scripts/check_loc.sh" in text
    assert "id: validate-shell-scripts" in text
    assert "scripts/validate-shell-scripts.sh" in text
    assert "id: frontend-prettier" in text
    assert "npm run format:check" in text


def test_lint_sh_runs_prettier_check_for_frontend() -> None:
    """`just lint --frontend` must fail on prettier drift (CI uses this)."""
    text = _LINT_SH.read_text(encoding="utf-8")
    assert "format:check" in text


def test_ci_runs_loc_shell_and_prettier_via_just() -> None:
    """ci.yml must invoke the just recipes that enforce LOC, shell, prettier."""
    text = _CI_YML.read_text(encoding="utf-8")
    assert "just lint --backend" in text
    assert "just lint --frontend" in text
    assert "just test --scripts" in text
    assert "prettier" in text.lower()
