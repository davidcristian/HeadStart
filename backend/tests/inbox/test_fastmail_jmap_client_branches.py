"""Branch coverage for the FastmailJmapClient (session/connection/fetch edges)."""

import json
from datetime import UTC, datetime

import httpx
import pytest
import respx
from httpx import Response

from app.inbox.fastmail_jmap import FastmailJmapClient

SESSION_URL = "https://api.fastmail.com/jmap/session"
API_URL = "https://api.fastmail.com/jmap/api/"


def _session_json(**overrides) -> dict:
    base = {
        "apiUrl": API_URL,
        "username": "user@fastmail.test",
        "primaryAccounts": {
            "urn:ietf:params:jmap:mail": "acct",
            "urn:ietf:params:jmap:core": "acct",
        },
    }
    base.update(overrides)
    return base


@respx.mock
def test_session_missing_api_url_raises() -> None:
    respx.get(SESSION_URL).mock(return_value=Response(200, json=_session_json(apiUrl="")))
    with pytest.raises(ValueError, match="apiUrl"):
        FastmailJmapClient("token").session()


@respx.mock
def test_session_missing_account_id_raises() -> None:
    respx.get(SESSION_URL).mock(return_value=Response(200, json=_session_json(primaryAccounts={})))
    with pytest.raises(ValueError, match="account id"):
        FastmailJmapClient("token").session()


@respx.mock
def test_session_missing_username_raises() -> None:
    respx.get(SESSION_URL).mock(return_value=Response(200, json=_session_json(username="")))
    with pytest.raises(ValueError, match="username"):
        FastmailJmapClient("token").session()


@respx.mock
def test_session_is_cached() -> None:
    route = respx.get(SESSION_URL).mock(return_value=Response(200, json=_session_json()))
    client = FastmailJmapClient("token")
    first = client.session()
    second = client.session()
    assert first is second
    assert route.call_count == 1


@respx.mock
def test_test_connection_returns_error_on_failure() -> None:
    respx.get(SESSION_URL).mock(return_value=Response(500))
    ok, error = FastmailJmapClient("token").test_connection()
    assert ok is False
    assert error


@respx.mock
def test_call_missing_method_responses_surfaces_via_test_connection() -> None:
    respx.get(SESSION_URL).mock(return_value=Response(200, json=_session_json()))
    respx.post(API_URL).mock(return_value=Response(200, json={"not": "methodResponses"}))
    # test_connection catches the ValueError raised inside _call and reports failure.
    ok, error = FastmailJmapClient("token").test_connection()
    assert ok is False
    assert error


@respx.mock
def test_fetch_with_since_received_naive_datetime() -> None:
    respx.get(SESSION_URL).mock(return_value=Response(200, json=_session_json()))

    def handler(request):
        payload = json.loads(request.content)
        methods = [c[0] for c in payload["methodCalls"]]
        if "Email/get" in methods:
            return Response(
                200,
                json={
                    "methodResponses": [
                        ["Email/query", {"ids": []}, "q0"],
                        ["Email/get", {"list": []}, "g0"],
                    ]
                },
            )
        # Mailbox/query + get for inbox role
        return Response(
            200,
            json={
                "methodResponses": [
                    ["Mailbox/query", {"ids": ["inbox-id"]}, "mq0"],
                    ["Mailbox/get", {"list": [{"id": "inbox-id", "role": "inbox"}]}, "mg0"],
                ]
            },
        )

    respx.post(API_URL).mock(side_effect=handler)
    naive = datetime(2026, 6, 1, 12, 0)  # no tzinfo -> naive branch (adds UTC)
    assert FastmailJmapClient("token").fetch_inbox_messages(since_received_at=naive, limit=5) == []
    aware = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)  # tzinfo set -> skips the replace
    assert FastmailJmapClient("token").fetch_inbox_messages(since_received_at=aware, limit=5) == []


def test_send_message_propagates_http_error() -> None:
    # A transport-level error surfaces as httpx.HTTPError (covered by adapter's
    # try/except); here we assert the client itself does not swallow it.
    client = FastmailJmapClient("token")
    with respx.mock:
        respx.get(SESSION_URL).mock(side_effect=httpx.ConnectError("boom"))
        with pytest.raises(httpx.HTTPError):
            client.session()
