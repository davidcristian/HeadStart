"""Chromium launch keeps the process sandbox unless explicitly disabled."""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.scrapers.playwright_browser import chromium_launch_args, close_browser, get_browser


@pytest.fixture(autouse=True)
def _reset_browser_pool() -> None:
    close_browser()
    yield
    close_browser()


def test_chromium_launch_args_keep_sandbox_by_default() -> None:
    """Default launch must not disable Chromium's process sandbox."""
    args = chromium_launch_args(no_sandbox=False)
    assert "--no-sandbox" not in args
    assert "--disable-dev-shm-usage" in args
    assert "--disable-gpu" in args


def test_chromium_launch_args_allow_local_no_sandbox_escape() -> None:
    """Local/test escape hatch may add --no-sandbox when explicitly requested."""
    args = chromium_launch_args(no_sandbox=True)
    assert "--no-sandbox" in args


def test_playwright_no_sandbox_rejected_outside_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production boots must refuse PLAYWRIGHT_NO_SANDBOX=true."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "a-real-long-random-production-secret-value")
    monkeypatch.setenv("CREDENTIALS_SECRET_KEY", "another-real-production-fernet-value")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("NTFY_DEFAULT_TOPIC", "jobs-0123456789abcdef")
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://app.example.com")
    monkeypatch.setenv("PLAYWRIGHT_NO_SANDBOX", "true")
    with pytest.raises(ValidationError, match="PLAYWRIGHT_NO_SANDBOX"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_playwright_no_sandbox_allowed_in_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """local/test may disable the Chromium sandbox for constrained hosts."""
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("PLAYWRIGHT_NO_SANDBOX", "true")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.playwright_no_sandbox is True


def _make_browser_mock() -> tuple[MagicMock, MagicMock]:
    browser = MagicMock()
    playwright = MagicMock()
    playwright.chromium.launch.return_value = browser
    cm = MagicMock()
    cm.__enter__.return_value = playwright
    return playwright, cm


def _patch_playwright(cm: MagicMock) -> Any:
    sync_playwright = MagicMock(return_value=cm)
    sync_api = MagicMock(sync_playwright=sync_playwright)
    return patch.dict(
        sys.modules,
        {
            "playwright": MagicMock(sync_api=sync_api),
            "playwright.sync_api": sync_api,
        },
    )


def test_get_browser_passes_sandboxed_launch_args() -> None:
    """Shared browser pool must launch Chromium without --no-sandbox by default."""
    playwright, cm = _make_browser_mock()
    with _patch_playwright(cm):
        get_browser()
    playwright.chromium.launch.assert_called_once()
    kwargs = playwright.chromium.launch.call_args.kwargs
    assert kwargs["headless"] is True
    assert "--no-sandbox" not in kwargs["args"]
    assert "--disable-dev-shm-usage" in kwargs["args"]
