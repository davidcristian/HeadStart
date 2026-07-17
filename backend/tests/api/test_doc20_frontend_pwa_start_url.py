"""Regression: frontend.md PWA start_url matches vite manifest (DOC-20)."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FRONTEND_DOC = _REPO_ROOT / "docs" / "modules" / "frontend.md"
_VITE_CONFIG = _REPO_ROOT / "frontend" / "vite.config.ts"


def _pwa_section(text: str) -> str:
    """Return the Progressive Web App section of frontend.md."""
    start = text.index("## Progressive Web App")
    rest = text[start:]
    next_heading = rest.find("\n## ", 1)
    return rest if next_heading < 0 else rest[:next_heading]


def test_frontend_md_pwa_opens_on_app_jobs() -> None:
    """PWA Install bullet must cite /app/jobs, not the legacy /jobs path."""
    section = _pwa_section(_FRONTEND_DOC.read_text(encoding="utf-8"))
    assert "opens on `/app/jobs`" in section
    assert "opens on `/jobs`" not in section
    # Routing section already documents the same start_url (self-consistency).
    full = _FRONTEND_DOC.read_text(encoding="utf-8")
    assert "start_url: /app/jobs" in full


def test_vite_manifest_start_url_is_app_jobs() -> None:
    """Guard against doc-only drift if the Vite PWA start_url changes."""
    src = _VITE_CONFIG.read_text(encoding="utf-8")
    assert 'start_url: "/app/jobs"' in src
