"""Lenient numeric coercion for untrusted scraper payloads."""

from __future__ import annotations

import math
from typing import Any


def coerce_count(raw: Any, default: int) -> int:
    """Coerce an untrusted total/count into a non-negative int.

    JSON ``Infinity`` / ``NaN`` (accepted by ``json.loads`` / httpx) would raise
    on bare ``int()``; a bad total falls back to ``default`` so the scrape stops
    cleanly instead of crashing or looping forever.
    """
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        return default
    if isinstance(raw, float) and not math.isfinite(raw):
        return default
    value = int(raw)
    return value if value >= 0 else default
