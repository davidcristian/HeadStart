"""Regression: CI quality gate uses shared just check entrypoints."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CI_YML = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_JUSTFILE = _REPO_ROOT / "justfile"
_CHECK_SH = _REPO_ROOT / "scripts" / "check.sh"
_BUILD_FRONTEND_SH = _REPO_ROOT / "scripts" / "build-frontend.sh"

# Hand-rolled tool invocations that must not appear as CI `run:` steps.
_HAND_ROLLED = re.compile(r"(?m)^\s+run:\s*.*\b(ruff|black|mypy|pytest|eslint|vitest|tsc)\b")


def test_check_sh_delegates_to_lint_typecheck_test() -> None:
    """scripts/check.sh must compose the same scripts local just check uses."""
    text = _CHECK_SH.read_text(encoding="utf-8")
    assert "scripts/lint.sh" in text
    assert "scripts/typecheck.sh" in text
    assert "scripts/test.sh" in text
    assert "--backend" in text
    assert "--frontend" in text
    assert "--scripts" in text


def test_justfile_check_calls_check_sh() -> None:
    """`just check` must invoke scripts/check.sh (not inline tool recipes)."""
    text = _JUSTFILE.read_text(encoding="utf-8")
    assert "check *args:" in text
    assert "scripts/check.sh" in text
    assert "build-frontend:" in text
    assert "scripts/build-frontend.sh" in text


def test_build_frontend_sh_runs_npm_build() -> None:
    """Frontend production build must go through a scripts/ entrypoint."""
    text = _BUILD_FRONTEND_SH.read_text(encoding="utf-8")
    assert "npm run build" in text


def test_ci_backend_uses_just_check_not_hand_rolled_tools() -> None:
    """Backend CI must call `just check --backend` (and scripts via check)."""
    text = _CI_YML.read_text(encoding="utf-8")
    assert "just check --backend" in text
    assert "just check --scripts" in text
    assert "just lint --backend" not in text
    assert "just typecheck --backend" not in text
    assert "just test --backend" not in text
    assert _HAND_ROLLED.search(text) is None


def test_ci_frontend_uses_just_check_and_build_frontend() -> None:
    """Frontend CI must call `just check --frontend` and `just build-frontend`."""
    text = _CI_YML.read_text(encoding="utf-8")
    assert "just check --frontend" in text
    assert "just build-frontend" in text
    assert "just lint --frontend" not in text
    assert "just typecheck --frontend" not in text
    assert "just test --frontend" not in text
    assert "npm run build" not in text
