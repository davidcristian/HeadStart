"""Regression: notifiers.md documents ntfy JSON publish to server root."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_NOTIFIERS_DOC = _REPO_ROOT / "docs" / "modules" / "notifiers.md"
_NTFY_ADAPTER = _REPO_ROOT / "backend" / "app" / "notifiers" / "adapters" / "ntfy.py"


def _ntfy_section(text: str) -> str:
    """Return the ntfy adapter section of notifiers.md."""
    start = text.index("## ntfy adapter")
    rest = text[start:]
    next_heading = rest.find("\n## ", 1)
    return rest if next_heading < 0 else rest[:next_heading]


def test_notifiers_md_describes_ntfy_json_publish_to_server_root() -> None:
    """Doc must describe JSON body POST to server_url, not path+header publish."""
    section = _ntfy_section(_NOTIFIERS_DOC.read_text(encoding="utf-8"))
    assert "{server_url}/{topic}" not in section
    assert "JSON" in section
    assert "server root" in section.lower() or "server_url" in section
    assert "`topic`" in section
    assert "`title`" in section
    assert "`priority`" in section
    assert "`tags`" in section
    assert "`click`" in section
    assert "Authorization: Bearer" in section


def test_ntfy_adapter_posts_json_to_server_root() -> None:
    """Guard against doc-only drift if the adapter reverts to path+header publish."""
    src = _NTFY_ADAPTER.read_text(encoding="utf-8")
    assert 'pinned_request(self._client, "POST", server_url, json=payload' in src
    assert '"topic": topic' in src
    assert 'f"Bearer {token}"' in src or '"Bearer' in src
