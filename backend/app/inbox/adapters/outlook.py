"""Microsoft Graph mailbox connector (OAuth + REST).

Fetches inbound mail via Graph message MIME, sends via sendMail, and routes folders
with mailFolders move.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.core.logging import get_logger
from app.inbox.base import MailboxConnector, register_mailbox
from app.inbox.outlook_ids import outlook_message_uid, uid_to_min_received_at
from app.inbox.parse import parse_rfc822
from app.inbox.types import (
    ConnectionTestResult,
    FetchResult,
    MailboxContext,
    MoveResult,
    OutboundMessage,
    OutlookMailboxConfig,
    SendResult,
)

logger = get_logger(__name__)

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_ID_HEADER = "x-ms-graph-id"


@register_mailbox("outlook")
class OutlookMailbox(MailboxConnector):
    """Read and send mail through Microsoft Graph."""

    def fetch_messages(
        self,
        ctx: MailboxContext,
        *,
        since_uid: int | None = None,
        limit: int = 50,
    ) -> FetchResult:
        config = self._config(ctx)
        headers = self._auth_headers(config)
        list_limit = max(limit * 3, limit)
        params: dict[str, str] = {
            "$orderby": "receivedDateTime asc",
            "$top": str(list_limit),
            "$select": "id,receivedDateTime",
        }
        if since_uid is not None:
            min_received = uid_to_min_received_at(since_uid).strftime("%Y-%m-%dT%H:%M:%SZ")
            params["$filter"] = f"receivedDateTime ge {min_received}"
        response = httpx.get(
            f"{GRAPH_API_BASE}/me/mailFolders/inbox/messages",
            headers=headers,
            params=params,
            timeout=30.0,
        )
        response.raise_for_status()
        entries = response.json().get("value") or []
        messages = []
        max_uid = since_uid
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            graph_id = entry.get("id")
            if not isinstance(graph_id, str) or not graph_id:
                continue
            received_at = _parse_graph_datetime(entry.get("receivedDateTime"))
            uid = outlook_message_uid(graph_id, received_at)
            if since_uid is not None and uid <= since_uid:
                continue
            raw = self._fetch_raw_message(headers, graph_id)
            if raw is None:
                continue
            message = parse_rfc822(uid, raw)
            message.raw_headers[GRAPH_ID_HEADER] = graph_id
            messages.append(message)
            max_uid = max(max_uid or 0, uid)
            if len(messages) >= limit:
                break
        messages.sort(key=lambda row: row.uid)
        return FetchResult(messages=messages, max_uid=max_uid)

    def send_message(self, ctx: MailboxContext, message: OutboundMessage) -> SendResult:
        config = self._config(ctx)
        headers = self._auth_headers(config)
        payload: dict[str, Any] = {
            "message": {
                "subject": message.subject,
                "body": {"contentType": "Text", "content": message.body},
                "toRecipients": [{"emailAddress": {"address": address}} for address in message.to],
                "from": {"emailAddress": {"address": config.email_address}},
            }
        }
        internet_headers: list[dict[str, str]] = []
        if message.in_reply_to:
            internet_headers.append({"name": "In-Reply-To", "value": message.in_reply_to})
        if message.references:
            internet_headers.append({"name": "References", "value": message.references})
        for key, value in message.extra_headers.items():
            internet_headers.append({"name": key, "value": value})
        if internet_headers:
            payload["message"]["internetMessageHeaders"] = internet_headers
        try:
            response = httpx.post(
                f"{GRAPH_API_BASE}/me/sendMail",
                headers=headers,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            return SendResult(status="sent")
        except httpx.HTTPError as exc:
            logger.warning("outlook send failed: %s", exc)
            return SendResult(status="failed", error=str(exc))

    def test_connection(self, ctx: MailboxContext) -> ConnectionTestResult:
        config = self._config(ctx)
        try:
            response = httpx.get(
                f"{GRAPH_API_BASE}/me",
                headers=self._auth_headers(config),
                params={"$select": "mail,userPrincipalName"},
                timeout=30.0,
            )
            response.raise_for_status()
            profile = response.json()
            email_address = profile.get("mail") or profile.get("userPrincipalName")
            if email_address != config.email_address:
                return ConnectionTestResult(
                    imap_ok=False,
                    smtp_ok=False,
                    error="Outlook profile email does not match stored credential.",
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
        """Move a Graph message into a mail folder (creates nested folders when needed)."""
        config = self._config(ctx)
        headers = self._auth_headers(config)
        graph_id = provider_message_id
        if not graph_id:
            return MoveResult(
                status="failed",
                destination=destination,
                error="Outlook routing requires graph_message_id on the classification.",
            )
        try:
            folder_id = self._ensure_folder_id(headers, destination)
            if folder_id is None:
                return MoveResult(
                    status="failed",
                    destination=destination,
                    error=f"Could not create Outlook folder '{destination}'",
                )
            response = httpx.post(
                f"{GRAPH_API_BASE}/me/messages/{graph_id}/move",
                headers=headers,
                json={"destinationId": folder_id},
                timeout=30.0,
            )
            response.raise_for_status()
            return MoveResult(status="moved", destination=destination)
        except httpx.HTTPError as exc:
            logger.warning("outlook move failed uid=%s dest=%s: %s", uid, destination, exc)
            return MoveResult(status="failed", destination=destination, error=str(exc))

    @staticmethod
    def _config(ctx: MailboxContext) -> OutlookMailboxConfig:
        if ctx.connector_type != "outlook":
            raise TypeError("OutlookMailbox requires connector_type='outlook'")
        config = ctx.config
        if not isinstance(config, OutlookMailboxConfig):
            raise TypeError("OutlookMailbox requires OutlookMailboxConfig")
        return config

    @staticmethod
    def _auth_headers(config: OutlookMailboxConfig) -> dict[str, str]:
        return {"Authorization": f"Bearer {config.access_token}"}

    @staticmethod
    def _fetch_raw_message(headers: dict[str, str], graph_id: str) -> bytes | None:
        response = httpx.get(
            f"{GRAPH_API_BASE}/me/messages/{graph_id}/$value",
            headers=headers,
            timeout=30.0,
        )
        if response.status_code >= 400:
            return None
        return response.content

    @staticmethod
    def _ensure_folder_id(headers: dict[str, str], folder_path: str) -> str | None:
        parts = [part.strip() for part in folder_path.split("/") if part.strip()]
        if not parts:
            return None
        parent_id: str | None = None
        for part in parts:
            parent_id = OutlookMailbox._find_or_create_child_folder(headers, parent_id, part)
            if parent_id is None:
                return None
        return parent_id

    @staticmethod
    def _find_or_create_child_folder(
        headers: dict[str, str],
        parent_id: str | None,
        display_name: str,
    ) -> str | None:
        if parent_id is None:
            list_url = f"{GRAPH_API_BASE}/me/mailFolders"
            create_url = f"{GRAPH_API_BASE}/me/mailFolders"
        else:
            list_url = f"{GRAPH_API_BASE}/me/mailFolders/{parent_id}/childFolders"
            create_url = f"{GRAPH_API_BASE}/me/mailFolders/{parent_id}/childFolders"
        for folder in OutlookMailbox._list_folders(headers, list_url):
            if folder.get("displayName") == display_name and isinstance(folder.get("id"), str):
                return folder["id"]
        response = httpx.post(
            create_url,
            headers=headers,
            json={"displayName": display_name},
            timeout=30.0,
        )
        if response.status_code >= 400:
            return None
        folder_id = response.json().get("id")
        return folder_id if isinstance(folder_id, str) else None

    @staticmethod
    def _list_folders(headers: dict[str, str], url: str) -> list[dict[str, Any]]:
        response = httpx.get(headers=headers, url=url, timeout=30.0)
        if response.status_code >= 400:
            return []
        folders = response.json().get("value")
        if not isinstance(folders, list):
            return []
        return [folder for folder in folders if isinstance(folder, dict)]


def _parse_graph_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None
