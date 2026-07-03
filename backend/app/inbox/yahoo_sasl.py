"""SASL OAUTHBEARER helpers for Yahoo IMAP and SMTP."""

from __future__ import annotations

YAHOO_IMAP_HOST = "imap.mail.yahoo.com"
YAHOO_IMAP_PORT = 993
YAHOO_SMTP_HOST = "smtp.mail.yahoo.com"
YAHOO_SMTP_PORT = 587
YAHOO_IMAP_MAILBOX = "Inbox"


def build_yahoo_oauth_bearer_string(
    email_address: str,
    access_token: str,
    *,
    host: str,
    port: int,
) -> str:
    """Build the initial client response for Yahoo OAUTHBEARER authentication."""
    return (
        f"n,a={email_address},\x01"
        f"host={host}\x01"
        f"port={port}\x01"
        f"auth=Bearer {access_token}\x01\x01"
    )
