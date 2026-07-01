"""Pluggable job-application adapters."""

from app.appliers.base import (
    Applier,
    available_appliers,
    get_applier,
    has_applier,
    register_applier,
)
from app.appliers.types import ApplyContext, ApplyResult

__all__ = [
    "Applier",
    "ApplyContext",
    "ApplyResult",
    "available_appliers",
    "get_applier",
    "has_applier",
    "register_applier",
]
