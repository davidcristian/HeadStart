"""Yahoo Mail mailbox connector (OAuth + IMAP/SMTP).

Yahoo does not expose a Gmail/Graph-style REST API. This adapter authenticates
with SASL OAUTHBEARER over IMAP and SMTP using OAuth tokens from Yahoo identity.
"""

from __future__ import annotations

import contextlib
import imaplib
import smtplib
from email.message import EmailMessage
from typing import Any, cast

from app.core.logging import get_logger
from app.inbox.base import MailboxConnector, register_mailbox
from app.inbox.parse import parse_rfc822
from app.inbox.types import (
    ConnectionTestResult,
    FetchResult,
    MailboxContext,
    MoveResult,
    OutboundMessage,
    SendResult,
    YahooMailboxConfig,
)
from app.inbox.yahoo_sasl import (
    YAHOO_IMAP_HOST,
    YAHOO_IMAP_MAILBOX,
    YAHOO_IMAP_PORT,
    YAHOO_SMTP_HOST,
    YAHOO_SMTP_PORT,
    build_yahoo_oauth_bearer_string,
)

logger = get_logger(__name__)


@register_mailbox("yahoo")
class YahooMailbox(MailboxConnector):
    """Read and send Yahoo Mail over OAuth-backed IMAP and SMTP."""

    def fetch_messages(
        self,
        ctx: MailboxContext,
        *,
        since_uid: int | None = None,
        limit: int = 50,
    ) -> FetchResult:
        config = self._config(ctx)
        client = self._imap_connect(config)
        try:
            client.select(YAHOO_IMAP_MAILBOX, readonly=True)
            criteria = f"UID {since_uid + 1}:*" if since_uid is not None else "ALL"
            status, data = client.uid("search", criteria)
            if status != "OK" or not data or not data[0]:
                return FetchResult(messages=[], max_uid=since_uid)
            uids = sorted(int(uid) for uid in data[0].split())
            if since_uid is not None:
                uids = [uid for uid in uids if uid > since_uid]
            if limit > 0:
                uids = uids[-limit:]
            messages = []
            max_uid = since_uid
            for uid in uids:
                status, fetched = client.uid("fetch", str(uid), "(RFC822)")
                if status != "OK" or not fetched or fetched[0] is None:
                    continue
                raw = fetched[0][1]
                if not isinstance(raw, bytes):
                    continue
                messages.append(parse_rfc822(uid, raw))
                max_uid = max(max_uid or 0, uid)
            return FetchResult(messages=messages, max_uid=max_uid)
        finally:
            self._imap_logout(client)

    def send_message(self, ctx: MailboxContext, message: OutboundMessage) -> SendResult:
        config = self._config(ctx)
        email = EmailMessage()
        email["Subject"] = message.subject
        email["From"] = config.email_address
        email["To"] = ", ".join(message.to)
        if message.in_reply_to:
            email["In-Reply-To"] = message.in_reply_to
        if message.references:
            email["References"] = message.references
        for key, value in message.extra_headers.items():
            email[key] = value
        email.set_content(message.body)
        try:
            smtp = self._smtp_connect(config)
            try:
                smtp.send_message(email)
            finally:
                with contextlib.suppress(smtplib.SMTPException):
                    smtp.quit()
            return SendResult(status="sent")
        except smtplib.SMTPException as exc:
            logger.warning("yahoo smtp send failed: %s", exc)
            return SendResult(status="failed", error=str(exc))

    def test_connection(self, ctx: MailboxContext) -> ConnectionTestResult:
        config = self._config(ctx)
        imap_ok = False
        smtp_ok = False
        errors: list[str] = []
        client: imaplib.IMAP4_SSL | None = None
        try:
            client = self._imap_connect(config)
            client.select(YAHOO_IMAP_MAILBOX, readonly=True)
            imap_ok = True
        except (imaplib.IMAP4.error, OSError, TimeoutError) as exc:
            errors.append(f"IMAP: {exc}")
        finally:
            if client is not None:
                self._imap_logout(client)
        try:
            smtp = self._smtp_connect(config)
            try:
                smtp.noop()
            finally:
                with contextlib.suppress(smtplib.SMTPException):
                    smtp.quit()
            smtp_ok = True
        except (smtplib.SMTPException, OSError, TimeoutError) as exc:
            errors.append(f"SMTP: {exc}")
        error = "; ".join(errors) if errors else None
        return ConnectionTestResult(
            imap_ok=imap_ok,
            smtp_ok=smtp_ok,
            error=error,
            details={"imap_mailbox": YAHOO_IMAP_MAILBOX, "email_address": config.email_address},
        )

    def move_message(
        self,
        ctx: MailboxContext,
        *,
        uid: int,
        destination: str,
        provider_message_id: str | None = None,
    ) -> MoveResult:
        """Move a message to another Yahoo IMAP folder."""
        if destination == YAHOO_IMAP_MAILBOX:
            return MoveResult(status="skipped", destination=destination)
        config = self._config(ctx)
        client = self._imap_connect(config)
        try:
            self._ensure_mailbox(client, destination)
            client.select(YAHOO_IMAP_MAILBOX, readonly=False)
            moved = self._uid_move(client, uid, destination)
            if moved:
                return MoveResult(status="moved", destination=destination)
            status, _ = client.uid("COPY", str(uid), destination)
            if status != "OK":
                return MoveResult(
                    status="failed",
                    destination=destination,
                    error="IMAP COPY failed",
                )
            status, _ = client.uid("STORE", str(uid), "+FLAGS", "(\\Deleted)")
            if status != "OK":
                return MoveResult(
                    status="failed",
                    destination=destination,
                    error="IMAP STORE \\Deleted failed",
                )
            client.expunge()
            return MoveResult(status="moved", destination=destination)
        except imaplib.IMAP4.error as exc:
            logger.warning("yahoo imap move failed uid=%s dest=%s: %s", uid, destination, exc)
            return MoveResult(status="failed", destination=destination, error=str(exc))
        finally:
            self._imap_logout(client)

    @staticmethod
    def _config(ctx: MailboxContext) -> YahooMailboxConfig:
        if ctx.connector_type != "yahoo":
            raise TypeError("YahooMailbox requires connector_type='yahoo'")
        config = ctx.config
        if not isinstance(config, YahooMailboxConfig):
            raise TypeError("YahooMailbox requires YahooMailboxConfig")
        return config

    @staticmethod
    def _imap_auth_string(config: YahooMailboxConfig) -> str:
        return build_yahoo_oauth_bearer_string(
            config.email_address,
            config.access_token,
            host=YAHOO_IMAP_HOST,
            port=YAHOO_IMAP_PORT,
        )

    @staticmethod
    def _smtp_auth_string(config: YahooMailboxConfig) -> str:
        return build_yahoo_oauth_bearer_string(
            config.email_address,
            config.access_token,
            host=YAHOO_SMTP_HOST,
            port=YAHOO_SMTP_PORT,
        )

    @classmethod
    def _imap_connect(cls, config: YahooMailboxConfig) -> imaplib.IMAP4_SSL:
        client = imaplib.IMAP4_SSL(YAHOO_IMAP_HOST, YAHOO_IMAP_PORT, timeout=30)
        auth_string = cls._imap_auth_string(config).encode("utf-8")
        client.authenticate("OAUTHBEARER", lambda _challenge: auth_string)
        return client

    @classmethod
    def _smtp_connect(cls, config: YahooMailboxConfig) -> smtplib.SMTP:
        smtp = smtplib.SMTP(YAHOO_SMTP_HOST, YAHOO_SMTP_PORT, timeout=30)
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        auth_bytes = cls._smtp_auth_string(config).encode("utf-8")

        def auth_response(_challenge: bytes | None) -> bytes:
            return auth_bytes

        smtp.auth(
            "OAUTHBEARER",
            cast(Any, auth_response),
            initial_response_ok=True,
        )
        return smtp

    @staticmethod
    def _imap_logout(client: imaplib.IMAP4_SSL) -> None:
        with contextlib.suppress(imaplib.IMAP4.error):
            client.logout()

    @staticmethod
    def _ensure_mailbox(client: imaplib.IMAP4_SSL, mailbox: str) -> None:
        with contextlib.suppress(imaplib.IMAP4.error):
            client.create(mailbox)

    @staticmethod
    def _uid_move(client: imaplib.IMAP4_SSL, uid: int, destination: str) -> bool:
        caps = client.capabilities or ()
        normalized = {
            (cap.decode() if isinstance(cap, bytes) else str(cap)).upper() for cap in caps
        }
        if "MOVE" not in normalized:
            return False
        status, _ = client.uid("MOVE", str(uid), destination)
        return status == "OK"
