"""Branch coverage for the FastmailJmapClient (send/identity/move edges)."""

import json

import pytest
import respx
from httpx import Response

from app.inbox.fastmail_jmap import FastmailJmapClient
from app.inbox.types import OutboundMessage

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
def test_send_message_builds_headers_and_identity() -> None:
    respx.get(SESSION_URL).mock(return_value=Response(200, json=_session_json()))
    captured = {}

    def handler(request):
        payload = json.loads(request.content)
        methods = [c[0] for c in payload["methodCalls"]]
        if "EmailSubmission/set" in methods:
            captured["draft"] = payload["methodCalls"][0][1]["create"]["draft"]
            return Response(
                200,
                json={
                    "methodResponses": [
                        ["Email/set", {"created": {"draft": {"id": "d1"}}}, "0"],
                        ["EmailSubmission/set", {"created": {"sendIt": {"id": "s1"}}}, "1"],
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
        # drafts mailbox lookup
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
    client = FastmailJmapClient("token")
    client.send_message(
        from_email="user@fastmail.test",
        message=OutboundMessage(
            to=["hr@company.test"],
            subject="Re: X",
            body="Body",
            in_reply_to="<r@x>",
            references="<a@x>",
            extra_headers={"X-HeadStart-Type": "auto-reply"},
        ),
    )
    header_names = {h["name"] for h in captured["draft"]["headers"]}
    assert {"In-Reply-To", "References", "X-HeadStart-Type"} <= header_names


@respx.mock
def test_identity_falls_back_to_first_when_no_email_match() -> None:
    respx.get(SESSION_URL).mock(return_value=Response(200, json=_session_json()))

    def handler(request):
        payload = json.loads(request.content)
        methods = [c[0] for c in payload["methodCalls"]]
        if "EmailSubmission/set" in methods:
            return Response(
                200,
                json={
                    "methodResponses": [
                        ["Email/set", {"created": {"draft": {"id": "d1"}}}, "0"],
                        ["EmailSubmission/set", {"created": {"sendIt": {"id": "s1"}}}, "1"],
                    ]
                },
            )
        if "Identity/get" in methods:
            # No identity email matches from_email, so the loop's inner guards are
            # exercised (non-matching email, then a match-but-empty-id) and the
            # code falls back to identities[0].id.
            return Response(
                200,
                json={
                    "methodResponses": [
                        [
                            "Identity/get",
                            {
                                "list": [
                                    {"id": "fallback-id", "email": "other@x"},
                                    {"id": "", "email": "user@fastmail.test"},
                                ]
                            },
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
    # No exception means the fallback identity id was used for the submission.
    FastmailJmapClient("token").send_message(
        from_email="user@fastmail.test",
        message=OutboundMessage(to=["hr@x"], subject="S", body="B"),
    )


@respx.mock
def test_identity_none_found_raises() -> None:
    respx.get(SESSION_URL).mock(return_value=Response(200, json=_session_json()))

    def handler(request):
        payload = json.loads(request.content)
        methods = [c[0] for c in payload["methodCalls"]]
        if "Identity/get" in methods:
            return Response(
                200,
                json={"methodResponses": [["Identity/get", {"list": []}, ""]]},
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
    with pytest.raises(ValueError, match="No JMAP identity"):
        FastmailJmapClient("token").send_message(
            from_email="user@fastmail.test",
            message=OutboundMessage(to=["hr@x"], subject="S", body="B"),
        )


@respx.mock
def test_identity_first_entry_missing_id_then_no_valid_raises() -> None:
    respx.get(SESSION_URL).mock(return_value=Response(200, json=_session_json()))

    def handler(request):
        payload = json.loads(request.content)
        methods = [c[0] for c in payload["methodCalls"]]
        if "Identity/get" in methods:
            return Response(
                200,
                json={"methodResponses": [["Identity/get", {"list": [{"email": "x@x"}]}, ""]]},
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
    with pytest.raises(ValueError, match="No JMAP identity"):
        FastmailJmapClient("token").send_message(
            from_email="user@fastmail.test",
            message=OutboundMessage(to=["hr@x"], subject="S", body="B"),
        )


@respx.mock
def test_move_message_noop_when_dest_equals_source() -> None:
    respx.get(SESSION_URL).mock(return_value=Response(200, json=_session_json()))
    posted = {"count": 0}

    def handler(request):
        posted["count"] += 1
        payload = json.loads(request.content)
        methods = [c[0] for c in payload["methodCalls"]]
        if "Mailbox/set" in methods:
            return Response(
                200,
                json={
                    "methodResponses": [
                        ["Mailbox/set", {"created": {"folder": {"id": "same-id"}}}, ""]
                    ]
                },
            )
        if "Email/set" in methods:  # pragma: no cover - not expected in this test
            raise AssertionError("Email/set must not be issued for a no-op move")
        # ensure_mailbox query -> not found (so it creates); role lookup -> same id
        filter_body = payload["methodCalls"][0][1].get("filter", {})
        if filter_body.get("name"):
            return Response(200, json={"methodResponses": [["Mailbox/query", {"ids": []}, ""]]})
        return Response(
            200,
            json={
                "methodResponses": [
                    ["Mailbox/query", {"ids": ["same-id"]}, "mq0"],
                    ["Mailbox/get", {"list": [{"id": "same-id", "role": "inbox"}]}, "mg0"],
                ]
            },
        )

    respx.post(API_URL).mock(side_effect=handler)
    # dest resolves to "same-id" which equals the inbox source -> early return, no Email/set
    FastmailJmapClient("token").move_message(email_id="M1", destination="Same")


@respx.mock
def test_send_message_raises_on_submission_not_created() -> None:
    respx.get(SESSION_URL).mock(return_value=Response(200, json=_session_json()))

    def handler(request):
        payload = json.loads(request.content)
        methods = [c[0] for c in payload["methodCalls"]]
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
    with pytest.raises(ValueError, match="EmailSubmission/set notCreated"):
        FastmailJmapClient("token").send_message(
            from_email="user@fastmail.test",
            message=OutboundMessage(to=["hr@x"], subject="S", body="B"),
        )


@respx.mock
def test_send_message_raises_when_created_missing() -> None:
    respx.get(SESSION_URL).mock(return_value=Response(200, json=_session_json()))

    def handler(request):
        payload = json.loads(request.content)
        methods = [c[0] for c in payload["methodCalls"]]
        if "EmailSubmission/set" in methods:
            return Response(
                200,
                json={
                    "methodResponses": [
                        ["Email/set", {}, "0"],
                        ["EmailSubmission/set", {"created": {"sendIt": {"id": "s1"}}}, "1"],
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
    with pytest.raises(ValueError, match="did not create draft"):
        FastmailJmapClient("token").send_message(
            from_email="user@fastmail.test",
            message=OutboundMessage(to=["hr@x"], subject="S", body="B"),
        )


@respx.mock
def test_send_message_raises_when_submission_created_missing() -> None:
    respx.get(SESSION_URL).mock(return_value=Response(200, json=_session_json()))

    def handler(request):
        payload = json.loads(request.content)
        methods = [c[0] for c in payload["methodCalls"]]
        if "EmailSubmission/set" in methods:
            return Response(
                200,
                json={
                    "methodResponses": [
                        ["Email/set", {"created": {"draft": {"id": "d1"}}}, "0"],
                        ["EmailSubmission/set", {}, "1"],
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
    with pytest.raises(ValueError, match="did not create submission"):
        FastmailJmapClient("token").send_message(
            from_email="user@fastmail.test",
            message=OutboundMessage(to=["hr@x"], subject="S", body="B"),
        )


@respx.mock
def test_move_message_raises_on_not_updated() -> None:
    respx.get(SESSION_URL).mock(return_value=Response(200, json=_session_json()))

    def handler(request):
        payload = json.loads(request.content)
        methods = [c[0] for c in payload["methodCalls"]]
        if "Email/set" in methods:
            return Response(
                200,
                json={
                    "methodResponses": [
                        [
                            "Email/set",
                            {"notUpdated": {"M1": {"type": "notFound", "description": "gone"}}},
                            "",
                        ]
                    ]
                },
            )
        filter_body = payload["methodCalls"][0][1].get("filter", {})
        if filter_body.get("name"):
            return Response(
                200,
                json={"methodResponses": [["Mailbox/query", {"ids": ["archive-id"]}, ""]]},
            )
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
    with pytest.raises(ValueError, match="notUpdated for M1"):
        FastmailJmapClient("token").move_message(email_id="M1", destination="Archive")
