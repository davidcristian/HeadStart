"""Types for careers-page URL detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SourceDetection:
    """Suggested source fields inferred from a job-board URL."""

    adapter_key: str
    suggested_name: str
    base_url: str
    default_config: dict[str, Any]
    query_url: str
