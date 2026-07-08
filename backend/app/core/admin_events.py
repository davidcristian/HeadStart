"""Structured admin mutation audit logging for operators (BIL-01)."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


def log_admin_user_update(
    *,
    actor_id: int,
    target_id: int,
    before: dict[str, Any],
    after: dict[str, Any],
) -> None:
    """Emit one admin audit line with actor, target, and before/after flags."""
    changed = {key: after[key] for key in after if before.get(key) != after[key]}
    if not changed:
        return
    before_changed = {key: before[key] for key in changed}
    parts = [
        "admin_event=user_update",
        f"actor_id={actor_id}",
        f"target_id={target_id}",
        f"before={_format_flags(before_changed)}",
        f"after={_format_flags(changed)}",
    ]
    logger.info(
        " ".join(parts),
        extra={
            "admin_event": "user_update",
            "actor_id": actor_id,
            "target_id": target_id,
            "before": before_changed,
            "after": changed,
        },
    )


def _format_flags(flags: dict[str, Any]) -> str:
    """Render flag dicts as compact key=value pairs for log scraping."""
    return ",".join(f"{key}={_format_value(value)}" for key, value in sorted(flags.items()))


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)
