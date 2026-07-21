"""Regression: frontend.md public routes include /subprocessors."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FRONTEND_DOC = _REPO_ROOT / "docs" / "modules" / "frontend.md"
_APP_TSX = _REPO_ROOT / "frontend" / "src" / "App.tsx"


def _routing_section(text: str) -> str:
    """Return the Routing section of frontend.md."""
    start = text.index("## Routing: public site vs. authenticated app")
    rest = text[start:]
    next_heading = rest.find("\n## ", 1)
    return rest if next_heading < 0 else rest[:next_heading]


def test_frontend_md_public_routes_include_subprocessors() -> None:
    """Public-routes bullet must list /subprocessors with the other legal pages."""
    section = _routing_section(_FRONTEND_DOC.read_text(encoding="utf-8"))
    # The Public bullet may wrap across lines; take through the next top-level bullet.
    start = section.index("- **Public**")
    rest = section[start:]
    next_bullet = rest.find("\n- **", 1)
    public_bullet = rest if next_bullet < 0 else rest[:next_bullet]
    assert "`/subprocessors`" in public_bullet
    assert "`/privacy`" in public_bullet
    assert "`/impressum`" in public_bullet


def test_app_registers_subprocessors_as_public_route() -> None:
    """Guard against doc-only drift if App.tsx drops the public route."""
    src = _APP_TSX.read_text(encoding="utf-8")
    assert 'path="/subprocessors"' in src
    assert "SubprocessorsPage" in src
