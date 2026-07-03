"""Fastmail JMAP session and method-call helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from app.inbox.fastmail_jmap_mailboxes import ensure_mailbox, mailbox_id_by_role
from app.inbox.fastmail_jmap_parse import JMAP_EMAIL_ID_HEADER
from app.inbox.fastmail_jmap_protocol import (
    FASTMAIL_SESSION_URL,
    INBOX_ROLE,
    JMAP_CORE,
    JMAP_MAIL,
    JMAP_SUBMISSION,
    JmapSession,
    response_list,
)
from app.inbox.types import OutboundMessage

__all__ = [
    "FASTMAIL_SESSION_URL",
    "INBOX_ROLE",
    "JMAP_EMAIL_ID_HEADER",
    "FastmailJmapClient",
    "JmapSession",
]


class FastmailJmapClient:
    """Thin JMAP client for Fastmail mailbox operations."""

    def __init__(self, api_token: str) -> None:
        self._api_token = api_token
        self._session: JmapSession | None = None

    def session(self) -> JmapSession:
        """Fetch and cache the JMAP session object."""
        if self._session is not None:
            return self._session
        response = httpx.get(
            FASTMAIL_SESSION_URL,
            headers=self._auth_headers(),
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        api_url = payload.get("apiUrl")
        primary = payload.get("primaryAccounts") or {}
        account_id = primary.get(JMAP_MAIL) or primary.get(JMAP_CORE)
        username = payload.get("username")
        if not isinstance(api_url, str) or not api_url:
            raise ValueError("JMAP session missing apiUrl")
        if not isinstance(account_id, str) or not account_id:
            raise ValueError("JMAP session missing mail account id")
        if not isinstance(username, str) or not username:
            raise ValueError("JMAP session missing username")
        self._session = JmapSession(api_url=api_url, account_id=account_id, username=username)
        return self._session

    def test_connection(self) -> tuple[bool, str | None]:
        """Verify the API token can read mail and submission capabilities."""
        try:
            session = self.session()
            self._call(
                session,
                using=[JMAP_CORE, JMAP_MAIL, JMAP_SUBMISSION],
                method_calls=[
                    ["Identity/get", {"accountId": session.account_id}, ""],
                    [
                        "Mailbox/query",
                        {"accountId": session.account_id, "filter": {"role": INBOX_ROLE}},
                        "",
                    ],
                ],
            )
            return True, None
        except (httpx.HTTPError, ValueError) as exc:
            return False, str(exc)

    def fetch_inbox_messages(
        self,
        *,
        since_received_at: datetime | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return raw JMAP Email objects from the inbox mailbox."""
        session = self.session()
        inbox_id = mailbox_id_by_role(self._call, session, INBOX_ROLE)
        query_args: dict[str, Any] = {
            "accountId": session.account_id,
            "filter": {"inMailbox": inbox_id},
            "sort": [{"property": "receivedAt", "isAscending": True}],
            "limit": max(limit * 3, limit),
        }
        if since_received_at is not None:
            if since_received_at.tzinfo is None:
                since_received_at = since_received_at.replace(tzinfo=UTC)
            query_args["filter"] = {
                "operator": "AND",
                "conditions": [
                    {"inMailbox": inbox_id},
                    {"after": since_received_at.isoformat().replace("+00:00", "Z")},
                ],
            }
        responses = self._call(
            session,
            using=[JMAP_CORE, JMAP_MAIL],
            method_calls=[
                ["Email/query", query_args, "q0"],
                [
                    "Email/get",
                    {
                        "accountId": session.account_id,
                        "#ids": {"resultOf": "q0", "name": "Email/query", "path": "/ids"},
                        "properties": [
                            "id",
                            "receivedAt",
                            "messageId",
                            "inReplyTo",
                            "references",
                            "from",
                            "to",
                            "subject",
                            "headers",
                            "bodyValues",
                            "textBody",
                        ],
                    },
                    "g0",
                ],
            ],
        )
        emails = response_list(responses, "Email/get")
        return emails[:limit]

    def send_message(self, *, from_email: str, message: OutboundMessage) -> None:
        """Create a draft and submit it via JMAP."""
        session = self.session()
        drafts_id = mailbox_id_by_role(self._call, session, "drafts")
        identity_id = self._identity_id_for_email(session, from_email)
        headers: list[dict[str, str]] = []
        if message.in_reply_to:
            headers.append({"name": "In-Reply-To", "value": message.in_reply_to})
        if message.references:
            headers.append({"name": "References", "value": message.references})
        for key, value in message.extra_headers.items():
            headers.append({"name": key, "value": value})
        draft: dict[str, Any] = {
            "from": [{"email": from_email}],
            "to": [{"email": address} for address in message.to],
            "subject": message.subject,
            "mailboxIds": {drafts_id: True},
            "keywords": {"$draft": True},
            "textBody": [{"partId": "body", "type": "text/plain"}],
            "bodyValues": {"body": {"charset": "utf-8", "value": message.body}},
        }
        if headers:
            draft["headers"] = headers
        self._call(
            session,
            using=[JMAP_CORE, JMAP_MAIL, JMAP_SUBMISSION],
            method_calls=[
                ["Email/set", {"accountId": session.account_id, "create": {"draft": draft}}, "0"],
                [
                    "EmailSubmission/set",
                    {
                        "accountId": session.account_id,
                        "onSuccessDestroyEmail": ["#sendIt"],
                        "create": {
                            "sendIt": {"emailId": "#draft", "identityId": identity_id},
                        },
                    },
                    "1",
                ],
            ],
        )

    def move_message(
        self,
        *,
        email_id: str,
        destination: str,
        source_mailbox_id: str | None = None,
    ) -> None:
        """Move one email into `destination` (mailbox name), creating the mailbox if needed."""
        session = self.session()
        dest_id = ensure_mailbox(self._call, session, destination)
        source_id = source_mailbox_id or mailbox_id_by_role(self._call, session, INBOX_ROLE)
        if dest_id == source_id:
            return
        update = {
            email_id: {
                "mailboxIds": {
                    dest_id: True,
                    source_id: None,
                }
            }
        }
        self._call(
            session,
            using=[JMAP_CORE, JMAP_MAIL],
            method_calls=[["Email/set", {"accountId": session.account_id, "update": update}, ""]],
        )

    def _identity_id_for_email(self, session: JmapSession, email: str) -> str:
        responses = self._call(
            session,
            using=[JMAP_CORE, JMAP_SUBMISSION],
            method_calls=[["Identity/get", {"accountId": session.account_id}, ""]],
        )
        identities = response_list(responses, "Identity/get")
        normalized = email.strip().lower()
        for identity in identities:
            identity_email = identity.get("email")
            if isinstance(identity_email, str) and identity_email.lower() == normalized:
                identity_id = identity.get("id")
                if isinstance(identity_id, str) and identity_id:
                    return identity_id
        if identities:
            identity_id = identities[0].get("id")
            if isinstance(identity_id, str) and identity_id:
                return identity_id
        raise ValueError(f"No JMAP identity found for {email}")

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_token}"}

    def _call(
        self,
        session: JmapSession,
        *,
        using: list[str],
        method_calls: list[list[Any]],
    ) -> list[list[Any]]:
        response = httpx.post(
            session.api_url,
            headers={**self._auth_headers(), "Content-Type": "application/json"},
            json={"using": using, "methodCalls": method_calls},
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        method_responses = payload.get("methodResponses")
        if not isinstance(method_responses, list):
            raise ValueError("JMAP response missing methodResponses")
        return method_responses
