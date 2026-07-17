"""Regression: api.md lists the /inbox/* router (DOC-09)."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_API_DOC = _REPO_ROOT / "docs" / "modules" / "api.md"
_INBOX_DOC = _REPO_ROOT / "docs" / "modules" / "inbox.md"
_ROUTER = _REPO_ROOT / "backend" / "app" / "api" / "v1" / "inbox.py"
_INIT = _REPO_ROOT / "backend" / "app" / "api" / "v1" / "__init__.py"

# Paths under /api/v1/inbox that inbox.py registers (DOC-09 evidence set).
_INBOX_PATHS = (
    "/inbox/credentials",
    "/inbox/gmail/authorize",
    "/inbox/gmail/callback",
    "/inbox/outlook/authorize",
    "/inbox/outlook/callback",
    "/inbox/yahoo/authorize",
    "/inbox/yahoo/callback",
    "/inbox/test",
    "/inbox/messages",
    "/inbox/classify",
    "/inbox/classifications",
    "/inbox/routing",
    "/inbox/route",
    "/inbox/draft-reply",
    "/inbox/reply-drafts",
    "/inbox/reply-send-logs",
)


def test_api_md_lists_inbox_endpoints() -> None:
    """Canonical v1 table must include the mounted /inbox/* routes."""
    text = _API_DOC.read_text(encoding="utf-8")
    for path in _INBOX_PATHS:
        assert f"`{path}`" in text, f"api.md missing {path}"
    assert "inbox.md" in text
    assert "INBOX_AGENT_ENABLED" in text


def test_inbox_router_still_mounted() -> None:
    """Guard against doc-only drift if the inbox router is removed or renamed."""
    init = _INIT.read_text(encoding="utf-8")
    router = _ROUTER.read_text(encoding="utf-8")
    assert 'prefix="/inbox"' in init
    assert "inbox.router" in init
    # Relative paths on the router must still exist for each documented row.
    for path in _INBOX_PATHS:
        relative = path.removeprefix("/inbox")
        assert re.search(
            rf'@router\.(get|post|put|patch|delete)\("{re.escape(relative)}"',
            router,
        ), f"inbox.py missing route for {relative}"
    inbox_doc = _INBOX_DOC.read_text(encoding="utf-8")
    assert "prefix `/api/v1/inbox`" in inbox_doc
    assert "INBOX_AGENT_ENABLED" in inbox_doc
