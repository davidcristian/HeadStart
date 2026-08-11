"""Regression: third-party attribution manifest stays wired."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_JUSTFILE = _REPO_ROOT / "justfile"
_SCRIPT = _REPO_ROOT / "scripts" / "generate-third-party-licenses.sh"
_ROOT_MANIFEST = _REPO_ROOT / "THIRD_PARTY_LICENSES.md"
_BACKEND_MANIFEST = _REPO_ROOT / "backend" / "THIRD_PARTY_LICENSES.md"
_FRONTEND_MANIFEST = _REPO_ROOT / "frontend" / "public" / "THIRD_PARTY_LICENSES.md"
_BACKEND_DOCKERFILE = _REPO_ROOT / "backend" / "Dockerfile"
_DEPLOYMENT_DOC = _REPO_ROOT / "docs" / "modules" / "deployment.md"


def test_third_party_licenses_manifest_committed() -> None:
    """Root + Docker build-context copies must exist and stay identical."""
    assert _ROOT_MANIFEST.is_file()
    assert _BACKEND_MANIFEST.is_file()
    assert _FRONTEND_MANIFEST.is_file()
    root = _ROOT_MANIFEST.read_text(encoding="utf-8")
    assert root == _BACKEND_MANIFEST.read_text(encoding="utf-8")
    assert root == _FRONTEND_MANIFEST.read_text(encoding="utf-8")
    assert "psycopg" in root
    assert "LGPL-3.0-only" in root
    # Pinning the react major froze the manifest instead of guarding it: the
    # assertion kept passing against a stale react@18 entry long after the app
    # moved to 19, so it failed the first time the file was regenerated.
    assert "react@" in root
    assert "just generate-third-party-licenses" in root


def test_generate_script_uses_pip_licenses_and_license_checker() -> None:
    """Generator must inventory backend locks and frontend production deps."""
    text = _SCRIPT.read_text(encoding="utf-8")
    assert "pip-licenses" in text
    assert "license-checker" in text
    assert "requirements.txt" in text
    assert "requirements-playwright.txt" in text
    assert "--production" in text


def test_justfile_exposes_generate_third_party_licenses() -> None:
    """Operators must share one just entrypoint for regenerating the manifest."""
    text = _JUSTFILE.read_text(encoding="utf-8")
    assert "generate-third-party-licenses:" in text
    assert "scripts/generate-third-party-licenses.sh" in text


def test_backend_dockerfile_copies_third_party_licenses() -> None:
    """API/worker images must bundle the attribution file."""
    text = _BACKEND_DOCKERFILE.read_text(encoding="utf-8")
    assert "COPY THIRD_PARTY_LICENSES.md" in text
    ignore = (_REPO_ROOT / "backend" / ".dockerignore").read_text(encoding="utf-8")
    assert "!THIRD_PARTY_LICENSES.md" in ignore
    fe_ignore = (_REPO_ROOT / "frontend" / ".dockerignore").read_text(encoding="utf-8")
    assert "!public/THIRD_PARTY_LICENSES.md" in fe_ignore


def test_deployment_doc_documents_third_party_licenses() -> None:
    """deployment.md must document regenerate + image bundle locations."""
    text = _DEPLOYMENT_DOC.read_text(encoding="utf-8")
    assert "THIRD_PARTY_LICENSES.md" in text
    assert "just generate-third-party-licenses" in text
    assert "!THIRD_PARTY_LICENSES.md" in text
