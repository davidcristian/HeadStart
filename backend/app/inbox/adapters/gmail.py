"""Gmail API mailbox connector (OAuth + REST).

Fetches inbound mail via users.messages.list/get and sends via users.messages.send.
Label routing uses users.messages.modify and users.labels.create.
"""

from __future__ import annotations

import base64
from datetime import datetime
from email.message import EmailMessage
from typing import Any

import httpx

from app.core.logging import get_logger
from app.inbox.base import MailboxConnector, register_mailbox
from app.inbox.gmail_ids import gmail_message_uid, parse_internal_date, uid_to_min_received_at
from app.inbox.parse import parse_rfc822
from app.inbox.types import (
    ConnectionTestResult,
    FetchResult,
    GmailMailboxConfig,
    MailboxContext,
    MoveResult,
    OutboundMessage,
    SendResult,
)

logger = get_logger(__name__)

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"
INBOX_LABEL_ID = "INBOX"
GMAIL_ID_HEADER = "x-gmail-id"


@register_mailbox("gmail")
class GmailMailbox(MailboxConnector):
    """Read and send mail through the Gmail API."""

    def fetch_messages(
        self,
        ctx: MailboxContext,
        *,
        since_uid: int | None = None,
        limit: int = 50,
    ) -> FetchResult:
        config = self._config(ctx)
        headers = self._auth_headers(config)
        candidates = self._list_unpolled_candidates(headers, since_uid=since_uid, limit=limit)
        messages = []
        max_uid = since_uid
        for uid, gmail_id in candidates:
            raw = self._fetch_raw_message(headers, gmail_id)
            if raw is None:
                continue
            message = parse_rfc822(uid, raw)
            message.raw_headers[GMAIL_ID_HEADER] = gmail_id
            messages.append(message)
            max_uid = max(max_uid or 0, uid)
        messages.sort(key=lambda row: row.uid)
        return FetchResult(messages=messages, max_uid=max_uid)

    def send_message(self, ctx: MailboxContext, message: OutboundMessage) -> SendResult:
        config = self._config(ctx)
        headers = self._auth_headers(config)
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
        raw = base64.urlsafe_b64encode(email.as_bytes()).decode("ascii")
        try:
            response = httpx.post(
                f"{GMAIL_API_BASE}/users/me/messages/send",
                headers=headers,
                json={"raw": raw},
                timeout=30.0,
            )
            response.raise_for_status()
            return SendResult(status="sent")
        except httpx.HTTPError as exc:
            logger.warning("gmail send failed: %s", exc)
            return SendResult(status="failed", error=str(exc))

    def test_connection(self, ctx: MailboxContext) -> ConnectionTestResult:
        config = self._config(ctx)
        try:
            response = httpx.get(
                f"{GMAIL_API_BASE}/users/me/profile",
                headers=self._auth_headers(config),
                timeout=30.0,
            )
            response.raise_for_status()
            profile = response.json()
            email_address = profile.get("emailAddress")
            if email_address != config.email_address:
                return ConnectionTestResult(
                    imap_ok=False,
                    smtp_ok=False,
                    error="Gmail profile email does not match stored credential.",
                )
            return ConnectionTestResult(
                imap_ok=True,
                smtp_ok=True,
                details={"email_address": email_address},
            )
        except httpx.HTTPError as exc:
            return ConnectionTestResult(imap_ok=False, smtp_ok=False, error=str(exc))

    def move_message(
        self,
        ctx: MailboxContext,
        *,
        uid: int,
        destination: str,
        provider_message_id: str | None = None,
    ) -> MoveResult:
        """Apply a Gmail label and remove INBOX (folder routing)."""
        config = self._config(ctx)
        headers = self._auth_headers(config)
        gmail_id = provider_message_id
        if not gmail_id:
            return MoveResult(
                status="failed",
                destination=destination,
                error="Gmail routing requires gmail_message_id on the classification.",
            )
        try:
            label_id = self._ensure_label_id(headers, destination)
            if label_id is None:
                return MoveResult(
                    status="failed",
                    destination=destination,
                    error=f"Could not create Gmail label '{destination}'",
                )
            response = httpx.post(
                f"{GMAIL_API_BASE}/users/me/messages/{gmail_id}/modify",
                headers=headers,
                json={"addLabelIds": [label_id], "removeLabelIds": [INBOX_LABEL_ID]},
                timeout=30.0,
            )
            response.raise_for_status()
            return MoveResult(status="moved", destination=destination)
        except httpx.HTTPError as exc:
            logger.warning("gmail move failed uid=%s dest=%s: %s", uid, destination, exc)
            return MoveResult(status="failed", destination=destination, error=str(exc))

    @staticmethod
    def _config(ctx: MailboxContext) -> GmailMailboxConfig:
        if ctx.connector_type != "gmail":
            raise TypeError("GmailMailbox requires connector_type='gmail'")
        config = ctx.config
        if not isinstance(config, GmailMailboxConfig):
            raise TypeError("GmailMailbox requires GmailMailboxConfig")
        return config

    @staticmethod
    def _auth_headers(config: GmailMailboxConfig) -> dict[str, str]:
        return {"Authorization": f"Bearer {config.access_token}"}

    def _list_unpolled_candidates(
        self,
        headers: dict[str, str],
        *,
        since_uid: int | None,
        limit: int,
    ) -> list[tuple[int, str]]:
        """Collect the oldest unpolled Gmail messages up to `limit`, ordered by
        received time. Gmail ids are not chronological, so each uid is derived from
        the message's internalDate and the server-side scan is narrowed with `after:`."""
        page_size = max(limit * 3, 100)
        max_pages = 20
        query: str | None = None
        if since_uid is not None:
            # Coarse server-side lower bound (with slack); the exact `uid <= since_uid`
            # skip below dedupes the overlap, so a wider window never drops mail.
            after = int(uid_to_min_received_at(since_uid).timestamp()) - 60
            query = f"after:{max(after, 0)}"
        candidates: list[tuple[int, str]] = []
        seen: set[str] = set()
        page_token: str | None = None
        for _ in range(max_pages):
            params: dict[str, str | int] = {
                "labelIds": INBOX_LABEL_ID,
                "maxResults": page_size,
            }
            if query is not None:
                params["q"] = query
            if page_token is not None:
                params["pageToken"] = page_token
            response = httpx.get(
                f"{GMAIL_API_BASE}/users/me/messages",
                headers=headers,
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            payload = response.json()
            for entry in payload.get("messages") or []:
                if not isinstance(entry, dict):
                    continue
                gmail_id = entry.get("id")
                if not isinstance(gmail_id, str) or not gmail_id or gmail_id in seen:
                    continue
                seen.add(gmail_id)
                received_at = self._message_received_at(headers, gmail_id)
                if received_at is None:
                    continue
                uid = gmail_message_uid(gmail_id, received_at)
                if since_uid is not None and uid <= since_uid:
                    continue
                candidates.append((uid, gmail_id))
            page_token = payload.get("nextPageToken")
            if not isinstance(page_token, str) or not page_token:
                break
        candidates.sort(key=lambda row: row[0])
        return candidates[:limit]

    @staticmethod
    def _fetch_raw_message(headers: dict[str, str], gmail_id: str) -> bytes | None:
        response = httpx.get(
            f"{GMAIL_API_BASE}/users/me/messages/{gmail_id}",
            headers=headers,
            params={"format": "raw"},
            timeout=30.0,
        )
        if response.status_code >= 400:
            return None
        raw_data = response.json().get("raw")
        if not isinstance(raw_data, str):
            return None
        padded = raw_data + "=" * (-len(raw_data) % 4)
        return base64.urlsafe_b64decode(padded.encode("ascii"))

    @staticmethod
    def _message_received_at(headers: dict[str, str], gmail_id: str) -> datetime | None:
        """Fetch a message's received time (Gmail internalDate) for uid ordering."""
        response = httpx.get(
            f"{GMAIL_API_BASE}/users/me/messages/{gmail_id}",
            headers=headers,
            params={"format": "metadata", "metadataHeaders": "Date"},
            timeout=30.0,
        )
        if response.status_code >= 400:
            return None
        return parse_internal_date(response.json().get("internalDate"))

    @staticmethod
    def _ensure_label_id(headers: dict[str, str], label_name: str) -> str | None:
        labels = GmailMailbox._list_labels(headers)
        for label in labels:
            if label.get("name") == label_name and isinstance(label.get("id"), str):
                return label["id"]
        response = httpx.post(
            f"{GMAIL_API_BASE}/users/me/labels",
            headers=headers,
            json={
                "name": label_name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
            timeout=30.0,
        )
        if response.status_code >= 400:
            return None
        label_id = response.json().get("id")
        return label_id if isinstance(label_id, str) else None

    @staticmethod
    def _list_labels(headers: dict[str, str]) -> list[dict[str, Any]]:
        response = httpx.get(
            f"{GMAIL_API_BASE}/users/me/labels",
            headers=headers,
            timeout=30.0,
        )
        if response.status_code >= 400:
            return []
        labels = response.json().get("labels")
        if not isinstance(labels, list):
            return []
        return [label for label in labels if isinstance(label, dict)]
