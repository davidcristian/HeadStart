"""Mailbox connector adapters — import to trigger self-registration."""

from app.inbox.adapters import fastmail as fastmail  # noqa: F401
from app.inbox.adapters import gmail as gmail  # noqa: F401
from app.inbox.adapters import imap_smtp as imap_smtp  # noqa: F401
from app.inbox.adapters import outlook as outlook  # noqa: F401
from app.inbox.adapters import yahoo as yahoo  # noqa: F401
