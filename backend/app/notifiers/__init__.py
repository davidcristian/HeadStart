"""Notifier subsystem: pluggable delivery channels.

Public API:
    from app.notifiers import get_notifier, available_notifiers, register_notifier
"""

from app.notifiers.base import (
    Notifier,
    available_notifiers,
    get_notifier,
    register_notifier,
)
from app.notifiers.types import DeliveryResult, NotifyContext

__all__ = [
    "DeliveryResult",
    "Notifier",
    "NotifyContext",
    "available_notifiers",
    "get_notifier",
    "register_notifier",
]
