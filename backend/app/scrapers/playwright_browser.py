"""Process-scoped Playwright browser reuse for Celery workers.

A headless Chromium instance is expensive to launch; workers keep one browser
open per child process and reuse it across scrapes. Browsers are created lazily
on first use and closed on worker shutdown.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_browser: Any | None = None
_playwright_cm: Any | None = None


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
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
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
