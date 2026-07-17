"""Regression: LGPL psycopg source/relink notice stays documented (XCT-25)."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "generate-third-party-licenses.sh"
_ROOT_MANIFEST = _REPO_ROOT / "THIRD_PARTY_LICENSES.md"
_BACKEND_MANIFEST = _REPO_ROOT / "backend" / "THIRD_PARTY_LICENSES.md"
_FRONTEND_MANIFEST = _REPO_ROOT / "frontend" / "public" / "THIRD_PARTY_LICENSES.md"
_DEPLOYMENT_DOC = _REPO_ROOT / "docs" / "modules" / "deployment.md"
_README = _REPO_ROOT / "README.md"


def test_third_party_licenses_documents_lgpl_psycopg_relink() -> None:
    """Manifest must explain LGPL §4 source/relink for unmodified pip psycopg."""
    root = _ROOT_MANIFEST.read_text(encoding="utf-8")
    assert root == _BACKEND_MANIFEST.read_text(encoding="utf-8")
    assert root == _FRONTEND_MANIFEST.read_text(encoding="utf-8")
    assert "LGPL-3.0 notice" in root
    assert "psycopg-binary" in root
    assert "Corresponding source" in root
    assert "Relink" in root
    assert "pip download" in root
    assert "does **not** vendor" in root


def test_generate_script_emits_lgpl_psycopg_notice() -> None:
    """Regenerating the manifest must keep the LGPL notice in the template."""
    text = _SCRIPT.read_text(encoding="utf-8")
    assert "LGPL-3.0 notice" in text
    assert "psycopg-binary" in text
    assert "Corresponding source" in text
    assert "Relink" in text


def test_docs_mention_lgpl_psycopg_notice() -> None:
    """deployment.md and README must point operators at the LGPL notice."""
    deployment = _DEPLOYMENT_DOC.read_text(encoding="utf-8")
    readme = _README.read_text(encoding="utf-8")
    assert "XCT-25" in deployment
    assert "LGPL-3.0 notice" in deployment
    assert "psycopg" in deployment
    assert "psycopg" in readme
    assert "relink" in readme.lower()
