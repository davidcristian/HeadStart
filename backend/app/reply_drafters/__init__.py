"""Pluggable reply drafters for recruiter follow-up email."""

from app.reply_drafters.base import (
    ReplyDrafter,
    available_reply_drafters,
    get_reply_drafter,
    register_reply_drafter,
)
from app.reply_drafters.types import ReplyDraftContext, ReplyDraftResult

__all__ = [
    "ReplyDraftContext",
    "ReplyDraftResult",
    "ReplyDrafter",
    "available_reply_drafters",
    "get_reply_drafter",
    "register_reply_drafter",
]
