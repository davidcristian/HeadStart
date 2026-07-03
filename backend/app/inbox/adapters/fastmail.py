"""Fastmail mailbox connector (API token + JMAP)."""

from __future__ import annotations

import httpx

from app.core.logging import get_logger
from app.inbox.base import MailboxConnector, register_mailbox
from app.inbox.fastmail_ids import fastmail_message_uid, uid_to_min_received_at
from app.inbox.fastmail_jmap import INBOX_ROLE, JMAP_EMAIL_ID_HEADER, FastmailJmapClient
from app.inbox.fastmail_jmap_parse import jmap_email_to_inbox_message
from app.inbox.types import (
    ConnectionTestResult,
    FastmailMailboxConfig,
    FetchResult,
    MailboxContext,
    MoveResult,
    OutboundMessage,
    SendResult,
)

logger = get_logger(__name__)


@register_mailbox("fastmail")
class FastmailMailbox(MailboxConnector):
    """Read and send mail through Fastmail's JMAP API."""

    def fetch_messages(
        self,
        ctx: MailboxContext,
        *,
        since_uid: int | None = None,
        limit: int = 50,
    ) -> FetchResult:
        config = self._config(ctx)
        client = FastmailJmapClient(config.api_token)
        since_received = uid_to_min_received_at(since_uid) if since_uid is not None else None
        emails = client.fetch_inbox_messages(since_received_at=since_received, limit=limit)
        messages = []
        max_uid = since_uid
        for email in emails:
            email_id = email.get("id")
            if not isinstance(email_id, str) or not email_id:
                continue
            received_at = jmap_email_to_inbox_message(email, 0).received_at
            uid = fastmail_message_uid(email_id, received_at)
            if since_uid is not None and uid <= since_uid:
                continue
            message = jmap_email_to_inbox_message(email, uid)
            messages.append(message)
            max_uid = max(max_uid or 0, uid)
        messages.sort(key=lambda row: row.uid)
        return FetchResult(messages=messages, max_uid=max_uid)

    def send_message(self, ctx: MailboxContext, message: OutboundMessage) -> SendResult:
        config = self._config(ctx)
        try:
            FastmailJmapClient(config.api_token).send_message(
                from_email=config.email_address,
                message=message,
            )
            return SendResult(status="sent")
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("fastmail send failed: %s", exc)
            return SendResult(status="failed", error=str(exc))

    def test_connection(self, ctx: MailboxContext) -> ConnectionTestResult:
        config = self._config(ctx)
        client = FastmailJmapClient(config.api_token)
        ok, error = client.test_connection()
        if ok and client.session().username.lower() != config.email_address.strip().lower():
            return ConnectionTestResult(
                imap_ok=False,
                smtp_ok=False,
                error="Fastmail session email does not match stored credential.",
            )
        return ConnectionTestResult(
            imap_ok=ok,
            smtp_ok=ok,
            error=error,
            details={"email_address": config.email_address},
        )

    def move_message(
        self,
        ctx: MailboxContext,
        *,
        uid: int,
        destination: str,
        provider_message_id: str | None = None,
    ) -> MoveResult:
        """Move a message into a named Fastmail mailbox folder."""
        config = self._config(ctx)
        email_id = provider_message_id
        if not email_id:
            return MoveResult(
                status="failed",
                destination=destination,
                error="Fastmail routing requires jmap_email_id on the classification.",
            )
        if destination.lower() == INBOX_ROLE:
            return MoveResult(status="skipped", destination=destination)
        try:
            FastmailJmapClient(config.api_token).move_message(
                email_id=email_id,
                destination=destination,
            )
            return MoveResult(status="moved", destination=destination)
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                "fastmail move failed uid=%s dest=%s email_id=%s: %s",
                uid,
                destination,
                email_id,
                exc,
            )
            return MoveResult(status="failed", destination=destination, error=str(exc))

    @staticmethod
    def jmap_email_id_from_headers(raw_headers: dict[str, str]) -> str | None:
        """Return the provider email id stored during fetch."""
        email_id = raw_headers.get(JMAP_EMAIL_ID_HEADER)
        return email_id if isinstance(email_id, str) and email_id else None

    @staticmethod
    def _config(ctx: MailboxContext) -> FastmailMailboxConfig:
        if ctx.connector_type != "fastmail":
            raise TypeError("FastmailMailbox requires connector_type='fastmail'")
        config = ctx.config
        if not isinstance(config, FastmailMailboxConfig):
            raise TypeError("FastmailMailbox requires FastmailMailboxConfig")
        return config
