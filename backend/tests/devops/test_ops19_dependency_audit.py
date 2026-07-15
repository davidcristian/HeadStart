"""Regression: backend SCA gate stays wired (OPS-19)."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CI_YML = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_DEPENDABOT = _REPO_ROOT / ".github" / "dependabot.yml"
_JUSTFILE = _REPO_ROOT / "justfile"
_AUDIT_SH = _REPO_ROOT / "scripts" / "audit-backend.sh"
_PYPROJECT = _REPO_ROOT / "backend" / "pyproject.toml"


def test_audit_backend_script_uses_disable_pip_on_hashed_locks() -> None:
    """pip-audit must read hashed lockfiles without a throwaway venv."""
    text = _AUDIT_SH.read_text(encoding="utf-8")
    assert "--disable-pip" in text
    assert "requirements.txt" in text
    assert "requirements-dev.txt" in text
    assert "requirements-playwright.txt" in text
    assert "pip_audit" in text


def test_justfile_exposes_audit_backend() -> None:
    """Operators and CI must share the same just entrypoint."""
    text = _JUSTFILE.read_text(encoding="utf-8")
    assert "audit-backend:" in text
    assert "scripts/audit-backend.sh" in text


def test_ci_runs_audit_backend_after_install() -> None:
    """ci.yml must fail the backend job when lockfile advisories appear."""
    text = _CI_YML.read_text(encoding="utf-8")
    assert "just audit-backend" in text
    install_at = text.index("./scripts/install-backend.sh --dev")
    audit_at = text.index("just audit-backend")
    assert install_at < audit_at


def test_dependabot_watches_backend_pip() -> None:
    """Dependabot must open weekly PRs for backend pip bumps (OPS-19)."""
    text = _DEPENDABOT.read_text(encoding="utf-8")
    assert "package-ecosystem: pip" in text
    assert "directory: /backend" in text


def test_pip_audit_is_a_dev_dependency() -> None:
    """Dev lock / install must ship pip-audit so CI does not curl it ad hoc."""
    text = _PYPROJECT.read_text(encoding="utf-8")
    assert "pip-audit" in text
