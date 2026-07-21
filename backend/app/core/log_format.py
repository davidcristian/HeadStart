"""LOG_FORMAT env parsing for structured vs text logs."""

from __future__ import annotations


def parse_log_format(value: object) -> str:
    """Normalize and validate LOG_FORMAT; only ``json`` and ``text`` are allowed."""
    if not isinstance(value, str):
        raise TypeError("LOG_FORMAT must be a string")
    normalized = value.strip().lower()
    if normalized not in {"json", "text"}:
        raise ValueError("LOG_FORMAT must be 'json' or 'text'")
    return normalized
