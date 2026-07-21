"""Regression: api.md lists GET/PATCH /summary-preferences."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_API_DOC = _REPO_ROOT / "docs" / "modules" / "api.md"
_SUMMARIES_DOC = _REPO_ROOT / "docs" / "modules" / "summaries.md"
_ROUTER = _REPO_ROOT / "backend" / "app" / "api" / "v1" / "summary_preferences.py"
_INIT = _REPO_ROOT / "backend" / "app" / "api" / "v1" / "__init__.py"


def test_api_md_lists_summary_preferences_endpoints() -> None:
    """Canonical v1 table must include the mounted summary-preferences routes."""
    text = _API_DOC.read_text(encoding="utf-8")
    assert "| GET    | `/summary-preferences`" in text
    assert "| PATCH  | `/summary-preferences`" in text
    assert "summaries.md" in text


def test_summary_preferences_router_still_mounted() -> None:
    """Guard against doc-only drift if the router is removed or renamed."""
    init = _INIT.read_text(encoding="utf-8")
    router = _ROUTER.read_text(encoding="utf-8")
    assert 'prefix="/summary-preferences"' in init
    assert "summary_preferences.router" in init
    assert "@router.get(" in router
    assert "@router.patch(" in router
    assert "response_model=SummaryPreferencesRead" in router
    summaries = _SUMMARIES_DOC.read_text(encoding="utf-8")
    assert "`GET /summary-preferences`" in summaries
    assert "`PATCH /summary-preferences`" in summaries
