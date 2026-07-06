"""Branch coverage for the Fastmail adapter (guards, skips, error paths)."""

import json
from datetime import UTC, datetime

import httpx
import pytest
import respx
from httpx import Response

from app.inbox.adapters.fastmail import FastmailMailbox
from app.inbox.fastmail_ids import fastmail_message_uid
from app.inbox.fastmail_jmap import JMAP_EMAIL_ID_HEADER
from app.inbox.types import (
    FastmailMailboxConfig,
    GmailMailboxConfig,
    MailboxContext,
    OutboundMessage,
)

CONFIG = FastmailMailboxConfig(email_address="user@fastmail.test", api_token="fmu1-test")
CTX = MailboxContext(connector_type="fastmail", config=CONFIG, user_id=1)
SESSION_URL = "https://api.fastmail.com/jmap/session"
API_URL = "https://api.fastmail.com/jmap/api/"
SESSION = {
    "apiUrl": API_URL,
    "username": "user@fastmail.test",
    "primaryAccounts": {
        "urn:ietf:params:jmap:mail": "acct",
        "urn:ietf:params:jmap:core": "acct",
    },
}
EMAIL_ID = "M1"
RECEIVED_AT = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)


def _mock_session(username: str = "user@fastmail.test") -> None:
    respx.get(SESSION_URL).mock(return_value=Response(200, json={**SESSION, "username": username}))


def _email_get_response(emails: list[dict]) -> Response:
    return Response(
        200,
        json={
            "methodResponses": [
                ["Email/query", {"ids": [e.get("id", "") for e in emails]}, "q0"],
                ["Email/get", {"list": emails}, "g0"],
            ]
        },
    )


def _inbox_role_response() -> Response:
    return Response(
        200,
        json={
            "methodResponses": [
                ["Mailbox/query", {"ids": ["inbox-id"]}, "mq0"],
                ["Mailbox/get", {"list": [{"id": "inbox-id", "role": "inbox"}]}, "mg0"],
            ]
        },
    )


def test_config_rejects_wrong_connector_type() -> None:
    ctx = MailboxContext(connector_type="gmail", config=CONFIG, user_id=1)
    with pytest.raises(TypeError, match="connector_type='fastmail'"):
        FastmailMailbox().fetch_messages(ctx)


def test_config_rejects_wrong_config_type() -> None:
    ctx = MailboxContext(
        connector_type="fastmail",
        config=GmailMailboxConfig(email_address="u@x.test", access_token="a", refresh_token="r"),
        user_id=1,
    )
    with pytest.raises(TypeError, match="FastmailMailboxConfig"):
        FastmailMailbox().fetch_messages(ctx)


def test_jmap_email_id_from_headers() -> None:
    assert FastmailMailbox.jmap_email_id_from_headers({JMAP_EMAIL_ID_HEADER: "M9"}) == "M9"
    assert FastmailMailbox.jmap_email_id_from_headers({JMAP_EMAIL_ID_HEADER: ""}) is None
    assert FastmailMailbox.jmap_email_id_from_headers({}) is None


@respx.mock
def test_fetch_skips_bad_id_and_already_seen_uid() -> None:
    _mock_session()
    good = {
        "id": EMAIL_ID,
        "receivedAt": RECEIVED_AT.isoformat().replace("+00:00", "Z"),
        "headers": [{"name": "From", "value": "hr@x"}, {"name": "Subject", "value": "S"}],
        "textBody": [{"partId": "body"}],
        "bodyValues": {"body": {"value": "hi"}},
    }
    bad = {"id": "", "receivedAt": RECEIVED_AT.isoformat().replace("+00:00", "Z")}

    def handler(request):
        methods = [c[0] for c in json.loads(request.content)["methodCalls"]]
        if "Email/get" in methods:
            return _email_get_response([bad, good])
        return _inbox_role_response()

    respx.post(API_URL).mock(side_effect=handler)
    # since_uid just below the good message's uid excludes nothing; a since_uid at
    # the message's own uid triggers the uid <= since_uid skip.
    good_uid = fastmail_message_uid(EMAIL_ID, RECEIVED_AT)
    skipped = FastmailMailbox().fetch_messages(CTX, since_uid=good_uid, limit=10)
    assert skipped.messages == []


@respx.mock
def test_send_message_failure_returns_failed() -> None:
    _mock_session()
    respx.post(API_URL).mock(side_effect=httpx.ConnectError("boom"))
    result = FastmailMailbox().send_message(
        CTX, OutboundMessage(to=["hr@x"], subject="S", body="B")
    )
    assert result.status == "failed"
    assert result.error


@respx.mock
def test_send_message_jmap_not_created_returns_failed() -> None:
    _mock_session()

    def handler(request):
        methods = [c[0] for c in json.loads(request.content)["methodCalls"]]
        if "EmailSubmission/set" in methods:
            return Response(
                200,
                json={
                    "methodResponses": [
                        ["Email/set", {"created": {"draft": {"id": "d1"}}}, "0"],
                        [
                            "EmailSubmission/set",
                            {
                                "notCreated": {
                                    "sendIt": {
                                        "type": "forbidden",
                                        "description": "blocked recipient",
                                    }
                                }
                            },
                            "1",
                        ],
                    ]
                },
            )
        if "Identity/get" in methods:
            return Response(
                200,
                json={
                    "methodResponses": [
                        [
                            "Identity/get",
                            {"list": [{"id": "id-1", "email": "user@fastmail.test"}]},
                            "",
                        ]
                    ]
                },
            )
        return Response(
            200,
            json={
                "methodResponses": [
                    ["Mailbox/query", {"ids": ["drafts-id"]}, "mq0"],
                    ["Mailbox/get", {"list": [{"id": "drafts-id", "role": "drafts"}]}, "mg0"],
                ]
            },
        )

    respx.post(API_URL).mock(side_effect=handler)
    result = FastmailMailbox().send_message(
        CTX, OutboundMessage(to=["hr@x"], subject="S", body="B")
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "notCreated" in result.error


@respx.mock
def test_test_connection_email_mismatch() -> None:
    _mock_session(username="different@fastmail.test")

    def handler(request):
        # Identity/get + Mailbox/query succeed so test_connection returns ok.
        return Response(
            200,
            json={
                "methodResponses": [
                    ["Identity/get", {"list": [{"id": "i", "email": "x"}]}, ""],
                    ["Mailbox/query", {"ids": ["inbox-id"]}, ""],
                ]
            },
        )

    respx.post(API_URL).mock(side_effect=handler)
    result = FastmailMailbox().test_connection(CTX)
    assert result.imap_ok is False
    assert result.smtp_ok is False
    assert "does not match" in (result.error or "")


def test_move_without_provider_id_fails() -> None:
    result = FastmailMailbox().move_message(CTX, uid=1, destination="HeadStart/General")
    assert result.status == "failed"
    assert "jmap_email_id" in (result.error or "")


def test_move_to_inbox_is_skipped() -> None:
    result = FastmailMailbox().move_message(
        CTX, uid=1, destination="inbox", provider_message_id="M1"
    )
    assert result.status == "skipped"


@respx.mock
def test_move_failure_returns_failed() -> None:
    _mock_session()
    respx.post(API_URL).mock(side_effect=httpx.ConnectError("boom"))
    result = FastmailMailbox().move_message(
        CTX, uid=1, destination="HeadStart/General", provider_message_id="M1"
    )
    assert result.status == "failed"
    assert result.error
