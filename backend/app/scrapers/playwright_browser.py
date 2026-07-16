"""Process-scoped Playwright browser reuse for Celery workers.

A headless Chromium instance is expensive to launch; workers keep one browser
open per child process and reuse it across scrapes. Browsers are created lazily
on first use and closed on worker shutdown.

Chromium keeps its process sandbox by default (OPS-27). ``--no-sandbox`` is
only added when ``PLAYWRIGHT_NO_SANDBOX=true`` in local/test.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_browser: Any | None = None
_playwright_cm: Any | None = None

# Container-friendly flags that do not disable Chromium's process sandbox.
_BASE_CHROMIUM_ARGS = (
    "--disable-dev-shm-usage",
    "--disable-gpu",
)


def chromium_launch_args(*, no_sandbox: bool | None = None) -> list[str]:
    """Build Chromium launch args; sandbox stays on unless explicitly disabled."""
    disable_sandbox = settings.playwright_no_sandbox if no_sandbox is None else no_sandbox
    args = list(_BASE_CHROMIUM_ARGS)
    if disable_sandbox:
        args.append("--no-sandbox")
    return args


def get_browser() -> Any:
    """Return the shared browser for this process, starting it if needed."""
    global _browser, _playwright_cm
    with _lock:
        if _browser is not None:
            return _browser
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - exercised only without extra
            raise RuntimeError(
                "The 'playwright' adapter requires the optional dependency. "
                'Install with: pip install -e ".[playwright]" && playwright install chromium'
            ) from exc

        _playwright_cm = sync_playwright()
        playwright = _playwright_cm.__enter__()
        _browser = playwright.chromium.launch(
            headless=True,
            args=chromium_launch_args(),
        )
        logger.info("playwright browser started")
        return _browser


def close_browser() -> None:
    """Shut down the shared browser for this process."""
    global _browser, _playwright_cm
    with _lock:
        if _browser is not None:
            _browser.close()
            _browser = None
        if _playwright_cm is not None:
            _playwright_cm.__exit__(None, None, None)
            _playwright_cm = None
            logger.info("playwright browser closed")
