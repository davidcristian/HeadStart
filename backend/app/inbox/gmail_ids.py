"""Stable integer UIDs for Gmail API message ids (used by inbox poll cursors)."""


def gmail_id_to_uid(gmail_id: str) -> int:
    """Map a Gmail API message id to the integer uid used across inbox tables."""
    normalized = gmail_id.strip().lower()
    if not normalized:
        raise ValueError("Gmail message id is empty")
    return int(normalized, 16)


def uid_to_gmail_id(uid: int) -> str:
    """Reverse `gmail_id_to_uid` for Gmail API calls."""
    if uid < 0:
        raise ValueError("Mailbox uid must be non-negative")
    return format(uid, "x")
