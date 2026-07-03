"""Tests for the Fastmail JMAP mailbox adapter (mocked HTTP)."""

import json
from datetime import UTC, datetime

import respx
from httpx import Response

from app.inbox.adapters.fastmail import FastmailMailbox
from app.inbox.fastmail_ids import fastmail_message_uid
from app.inbox.types import FastmailMailboxConfig, MailboxContext, OutboundMessage

CONFIG = FastmailMailboxConfig(
    email_address="user@fastmail.test",
    api_token="fmu1-test-token",
)
CTX = MailboxContext(connector_type="fastmail", config=CONFIG, user_id=1)
EMAIL_ID = "Me4672cc07651aaf91ab4cee6"
RECEIVED_AT = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
SESSION = {
    "apiUrl": "https://api.fastmail.com/jmap/api/",
    "username": "user@fastmail.test",
    "primaryAccounts": {
        "urn:ietf:params:jmap:mail": "u12345678",
        "urn:ietf:params:jmap:core": "u12345678",
    },
}


def _mock_session() -> None:
    respx.get("https://api.fastmail.com/jmap/session").mock(
        return_value=Response(200, json=SESSION)
    )


def _jmap_response(*method_responses: list[object]) -> Response:
    return Response(200, json={"methodResponses": list(method_responses)})


def _mailbox_by_role_response(role: str, mailbox_id: str) -> Response:
    return _jmap_response(
        ["Mailbox/query", {"ids": [mailbox_id], "filter": {"role": role}}, "mq0"],
        [
            "Mailbox/get",
            {"list": [{"id": mailbox_id, "name": role.title(), "role": role}]},
            "mg0",
        ],
    )


def _route_jmap_request(request: object) -> Response:
    payload = json.loads(request.content)  # type: ignore[attr-defined]
    calls = payload.get("methodCalls") or []
    methods = [call[0] for call in calls if isinstance(call, list) and call]
    if "Email/get" in methods:
        return _jmap_response(
            ["Email/query", {"accountId": "u12345678", "ids": [EMAIL_ID]}, "q0"],
            [
                "Email/get",
                {
                    "list": [
                        {
                            "id": EMAIL_ID,
                            "receivedAt": RECEIVED_AT.isoformat().replace("+00:00", "Z"),
                            "from": [{"email": "hr@company.test"}],
                            "to": [{"email": "user@fastmail.test"}],
                            "subject": "Interview follow-up",
                            "textBody": [{"partId": "body", "type": "text/plain"}],
                            "bodyValues": {
                                "body": {"value": "Please reply with your availability."}
                            },
                        }
                    ]
                },
                "g0",
            ],
        )
    if "EmailSubmission/set" in methods:
        return _jmap_response(
            ["Email/set", {"created": {"draft": {"id": EMAIL_ID}}}, "0"],
            ["EmailSubmission/set", {"created": {"sendIt": {"id": "S1"}}}, "1"],
        )
    if "Email/set" in methods and "update" in json.dumps(payload):
        return _jmap_response(["Email/set", {"updated": {EMAIL_ID: None}}, ""])
    if "Mailbox/query" in methods:
        filter_body = calls[0][1].get("filter", {}) if calls else {}
        if filter_body.get("name") == "HeadStart/General":
            return _jmap_response(["Mailbox/query", {"ids": ["dest-id"]}, ""])
        role = filter_body.get("role", "inbox")
        mailbox_id = "drafts-id" if role == "drafts" else "inbox-id"
        return _mailbox_by_role_response(str(role), mailbox_id)
    if "Identity/get" in methods:
        return _jmap_response(
            [
                "Identity/get",
                {"list": [{"id": "identity-1", "email": "user@fastmail.test"}]},
                "",
            ]
        )
    return _jmap_response(["Mailbox/query", {"ids": []}, ""])


@respx.mock
def test_fetch_messages_parses_inbox() -> None:
    _mock_session()
    respx.post("https://api.fastmail.com/jmap/api/").mock(side_effect=_route_jmap_request)
    result = FastmailMailbox().fetch_messages(CTX, limit=10)
    assert len(result.messages) == 1
    assert result.messages[0].uid == fastmail_message_uid(EMAIL_ID, RECEIVED_AT)
    assert result.messages[0].subject == "Interview follow-up"
    assert result.messages[0].raw_headers["x-headstart-jmap-id"] == EMAIL_ID


@respx.mock
def test_send_message_uses_jmap_submission() -> None:
    _mock_session()
    route = respx.post("https://api.fastmail.com/jmap/api/").mock(side_effect=_route_jmap_request)
    result = FastmailMailbox().send_message(
        CTX,
        OutboundMessage(
            to=["recruiter@company.test"],
            subject="Re: Interview",
            body="I am free Tuesday afternoon.",
        ),
    )
    assert result.status == "sent"
    assert route.called


@respx.mock
def test_test_connection_checks_session() -> None:
    _mock_session()
    respx.post("https://api.fastmail.com/jmap/api/").mock(side_effect=_route_jmap_request)
    result = FastmailMailbox().test_connection(CTX)
    assert result.imap_ok is True
    assert result.smtp_ok is True
    assert result.error is None


@respx.mock
def test_move_message_updates_mailbox_ids() -> None:
    _mock_session()
    route = respx.post("https://api.fastmail.com/jmap/api/").mock(side_effect=_route_jmap_request)
    uid = fastmail_message_uid(EMAIL_ID, RECEIVED_AT)
    result = FastmailMailbox().move_message(
        CTX,
        uid=uid,
        destination="HeadStart/General",
        provider_message_id=EMAIL_ID,
    )
    assert result.status == "moved"
    assert route.called
