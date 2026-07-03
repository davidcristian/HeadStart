"""Inbox subsystem: pluggable mailbox connectors for dev-only email triage."""

from app.inbox.base import available_mailboxes, get_mailbox

__all__ = ["available_mailboxes", "get_mailbox"]
