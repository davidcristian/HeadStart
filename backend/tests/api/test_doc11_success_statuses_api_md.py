"""Regression: api.md documents non-default success statuses (DOC-11)."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_API_DOC = _REPO_ROOT / "docs" / "modules" / "api.md"

# POST creates that declare status_code=201 (DOC-11 evidence set).
_CREATE_DOC_PATHS = (
    "/auth/register",
    "/sources",
    "/searches",
    "/targets",
    "/credentials",
    "/admin/promo-codes",
)

_CREATE_ROUTER_FILES = (
    "backend/app/api/v1/auth.py",
    "backend/app/api/v1/sources.py",
    "backend/app/api/v1/searches.py",
    "backend/app/api/v1/targets.py",
    "backend/app/api/v1/credentials.py",
    "backend/app/api/v1/admin.py",
)


def test_api_md_documents_create_and_webhook_success_statuses() -> None:
    """Canonical API map must call out 201 creates and 204 webhook."""
    text = _API_DOC.read_text(encoding="utf-8")
    assert "### Success status codes (DOC-11)" in text
    assert "| **201** |" in text
    assert "| **204** |" in text
    assert "`POST /billing/webhook`" in text
    for path in _CREATE_DOC_PATHS:
        assert path in text, f"api.md missing create path {path}"
        assert re.search(
            rf"\| POST\s+\| `{re.escape(path)}`\s+\|.*HTTP \*\*201\*\*",
            text,
        ), f"api.md create row missing HTTP 201 for {path}"
    assert re.search(
        r"\| POST\s+\| `/billing/webhook`\s+\|.*HTTP \*\*204\*\*",
        text,
    )


def test_create_and_webhook_routes_still_use_non_default_statuses() -> None:
    """Guard against doc-only drift if routers drop 201/204."""
    for rel in _CREATE_ROUTER_FILES:
        src = (_REPO_ROOT / rel).read_text(encoding="utf-8")
        assert (
            "HTTP_201_CREATED" in src or "status_code=201" in src
        ), f"{rel} missing 201 create status"

    auth = (_REPO_ROOT / "backend/app/api/v1/auth.py").read_text(encoding="utf-8")
    assert '@router.post("/register"' in auth

    admin = (_REPO_ROOT / "backend/app/api/v1/admin.py").read_text(encoding="utf-8")
    assert '@router.post("/promo-codes"' in admin

    billing = (_REPO_ROOT / "backend/app/api/v1/billing.py").read_text(encoding="utf-8")
    assert '@router.post("/webhook", status_code=204)' in billing
