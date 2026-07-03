"""Per-adapter request pacing for polite scraping.

Rate limits are resolved from the merged source/search config, falling back to
per-adapter defaults. A limit of zero disables throttling for that scrape.
"""

from __future__ import annotations

import time
from threading import Lock
from typing import Any

CONFIG_KEY = "rate_limit_min_interval_seconds"

# Conservative defaults: public JSON APIs are lighter than HTML/Playwright.
ADAPTER_DEFAULTS: dict[str, float] = {
    "greenhouse": 1.0,
    "lever": 1.0,
    "ashby": 1.0,
    "smartrecruiters": 1.0,
    "workday": 2.5,
    "amazon_jobs": 2.5,
    "apple_careers": 3.0,
    "google_careers": 2.5,
    "meta_careers": 3.0,
    "microsoft_careers": 2.5,
    "shopify_careers": 3.0,
    "uber_careers": 2.5,
    "indeed": 5.0,
    "linkedin": 7.5,
    "generic_html": 2.0,
    "playwright": 5.0,
}


class RateLimiter:
    """Enforce a minimum gap between consecutive outbound requests."""

    def __init__(self, min_interval_seconds: float) -> None:
        if min_interval_seconds < 0:
            raise ValueError("min_interval_seconds must be >= 0")
        self._min_interval = min_interval_seconds
        self._last_at: float | None = None
        self._lock = Lock()

    @property
    def min_interval_seconds(self) -> float:
        return self._min_interval

    def wait(self) -> None:
        """Block until another request is allowed."""
        if self._min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            if self._last_at is not None:
                elapsed = now - self._last_at
                if elapsed < self._min_interval:
                    time.sleep(self._min_interval - elapsed)
                    now = time.monotonic()
            self._last_at = now


def resolve_min_interval(adapter_key: str, config: dict[str, Any]) -> float:
    """Return the minimum seconds between requests for one scrape."""
    if CONFIG_KEY in config:
        value = config[CONFIG_KEY]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"{CONFIG_KEY} must be a non-negative number")
        if value < 0:
            raise ValueError(f"{CONFIG_KEY} must be a non-negative number")
        return float(value)
    return ADAPTER_DEFAULTS.get(adapter_key, 0.0)
