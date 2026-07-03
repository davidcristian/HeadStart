"""IMAP + SMTP mailbox connector.

Fetches inbound mail via IMAP (UID SEARCH/FETCH) and sends outbound mail via SMTP.
Uses the Python stdlib only — no extra dependencies.

Connector config shape: see `MailboxConfig` in `app.inbox.types`.
"""

from __future__ import annotations

import contextlib
import imaplib
import smtplib
from email.message import EmailMessage

from app.core.logging import get_logger
from app.inbox.base import MailboxConnector, register_mailbox
from app.inbox.parse import parse_rfc822
from app.inbox.types import (
    ConnectionTestResult,
    FetchResult,
    MailboxConfig,
    MailboxContext,
    OutboundMessage,
    SendResult,
)

logger = get_logger(__name__)


@register_mailbox("imap_smtp")
class ImapSmtpMailbox(MailboxConnector):
    """Read mail over IMAP and send over SMTP."""

    def fetch_messages(
        self,
        ctx: MailboxContext,
        *,
        since_uid: int | None = None,
        limit: int = 50,
    ) -> FetchResult:
        config = ctx.config
        client = self._imap_connect(config)
        try:
            client.select(config.imap_mailbox, readonly=True)
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
        config = ctx.config
        email = EmailMessage()
        email["Subject"] = message.subject
        email["From"] = config.smtp_from or config.imap_user
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
            logger.warning("smtp send failed: %s", exc)
            return SendResult(status="failed", error=str(exc))

    def test_connection(self, ctx: MailboxContext) -> ConnectionTestResult:
        config = ctx.config
        imap_ok = False
        smtp_ok = False
        errors: list[str] = []
        client: imaplib.IMAP4 | imaplib.IMAP4_SSL | None = None
        try:
            client = self._imap_connect(config)
            client.select(config.imap_mailbox, readonly=True)
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
            details={"imap_mailbox": config.imap_mailbox},
        )

    @staticmethod
    def _imap_connect(config: MailboxConfig) -> imaplib.IMAP4 | imaplib.IMAP4_SSL:
        if config.imap_use_ssl:
            client: imaplib.IMAP4 | imaplib.IMAP4_SSL = imaplib.IMAP4_SSL(
                config.imap_host, config.imap_port, timeout=30
            )
        else:
            client = imaplib.IMAP4(config.imap_host, config.imap_port, timeout=30)
        client.login(config.imap_user, config.imap_password)
        return client

    @staticmethod
    def _imap_logout(client: imaplib.IMAP4 | imaplib.IMAP4_SSL) -> None:
        with contextlib.suppress(imaplib.IMAP4.error):
            client.logout()

    @staticmethod
    def _smtp_connect(config: MailboxConfig) -> smtplib.SMTP:
        smtp = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30)
        if config.smtp_use_tls:
            smtp.starttls()
        smtp_user = config.smtp_user or config.imap_user
        smtp_password = config.smtp_password or config.imap_password
        if smtp_user:
            smtp.login(smtp_user, smtp_password)
        return smtp
