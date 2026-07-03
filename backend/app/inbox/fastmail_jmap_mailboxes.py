"""Fastmail JMAP mailbox lookup and creation helpers."""

from __future__ import annotations

from typing import Any

from app.inbox.fastmail_jmap_protocol import (
    JMAP_CORE,
    JMAP_MAIL,
    JmapSession,
    response_created,
    response_ids,
    response_list,
)


def mailbox_id_by_role(
    call: Any,
    session: JmapSession,
    role: str,
) -> str:
    """Resolve a mailbox id by JMAP role (e.g. inbox, drafts)."""
    responses = call(
        session,
        using=[JMAP_CORE, JMAP_MAIL],
        method_calls=[
            [
                "Mailbox/query",
                {"accountId": session.account_id, "filter": {"role": role}},
                "mq0",
            ],
            [
                "Mailbox/get",
                {
                    "accountId": session.account_id,
                    "#ids": {"resultOf": "mq0", "name": "Mailbox/query", "path": "/ids"},
                    "properties": ["id", "name", "role"],
                },
                "mg0",
            ],
        ],
    )
    mailboxes = response_list(responses, "Mailbox/get")
    if not mailboxes:
        raise ValueError(f"Mailbox with role '{role}' was not found")
    mailbox_id = mailboxes[0].get("id")
    if not isinstance(mailbox_id, str) or not mailbox_id:
        raise ValueError(f"Mailbox with role '{role}' has no id")
    return mailbox_id


def ensure_mailbox(call: Any, session: JmapSession, name: str) -> str:
    """Return an existing mailbox id or create one by display name."""
    responses = call(
        session,
        using=[JMAP_CORE, JMAP_MAIL],
        method_calls=[
            [
                "Mailbox/query",
                {"accountId": session.account_id, "filter": {"name": name}},
                "",
            ],
        ],
    )
    ids = response_ids(responses, "Mailbox/query")
    if ids:
        return ids[0]
    create_responses = call(
        session,
        using=[JMAP_CORE, JMAP_MAIL],
        method_calls=[
            [
                "Mailbox/set",
                {
                    "accountId": session.account_id,
                    "create": {"folder": {"name": name}},
                },
                "",
            ],
        ],
    )
    created = response_created(create_responses, "Mailbox/set")
    mailbox_id = created.get("id")
    if not isinstance(mailbox_id, str) or not mailbox_id:
        raise ValueError(f"Could not create mailbox '{name}'")
    return mailbox_id
