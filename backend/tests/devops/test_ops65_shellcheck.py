"""Regression: shell validation runs shellcheck at warning+ (OPS-65)."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_VALIDATE = _REPO_ROOT / "scripts" / "validate-shell-scripts.sh"
_CI_YML = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_SETUP = _REPO_ROOT / "scripts" / "setup.sh"


def test_validate_shell_scripts_runs_shellcheck_warning_floor() -> None:
    """Gate must invoke shellcheck (not bash -n alone) at -S warning (OPS-65)."""
    text = _VALIDATE.read_text(encoding="utf-8")
    assert "shellcheck" in text
    assert "-S warning" in text
    assert "OPS-65" in text
    assert "have shellcheck || die" in text


def test_ci_installs_shellcheck_before_scripts_gate() -> None:
    """ubuntu-latest does not ship shellcheck; CI must install it first."""
    text = _CI_YML.read_text(encoding="utf-8")
    assert "apt-get install" in text and "shellcheck" in text
    assert "just check --scripts" in text


def test_setup_warns_when_shellcheck_missing() -> None:
    """Host preflight should surface a missing shellcheck like other gate tools."""
    text = _SETUP.read_text(encoding="utf-8")
    assert "shellcheck" in text
