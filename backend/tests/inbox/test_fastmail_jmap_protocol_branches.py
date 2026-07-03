"""Branch coverage for JMAP response parsing helpers and mailbox lookups."""

import pytest

from app.inbox.fastmail_jmap_mailboxes import ensure_mailbox, mailbox_id_by_role
from app.inbox.fastmail_jmap_protocol import (
    JmapSession,
    response_created,
    response_ids,
    response_list,
)

SESSION = JmapSession(api_url="https://api/", account_id="acct", username="u@x")


# --------------------------------------------------------------------------- #
# response_list
# --------------------------------------------------------------------------- #


def test_response_list_variants() -> None:
    # method name mismatch / short row -> skipped, then found
    responses = [
        ["Other", {"list": [{"id": 1}]}, ""],
        ["Short"],
        ["Target", {"list": [{"id": "a"}, "not-a-dict"]}, ""],
    ]
    assert response_list(responses, "Target") == [{"id": "a"}]

    # body not a dict -> returns []
    assert response_list([["Target", "not-a-dict", ""]], "Target") == []

    # body dict but list missing/not-a-list -> loop ends -> []
    assert response_list([["Target", {"list": "nope"}, ""]], "Target") == []

    # nothing matches -> []
    assert response_list([], "Target") == []


# --------------------------------------------------------------------------- #
# response_ids
# --------------------------------------------------------------------------- #


def test_response_ids_variants() -> None:
    responses = [
        ["Short"],
        ["Other", {"ids": ["x"]}, ""],
        ["Target", {"ids": ["a", 5, "b"]}, ""],
    ]
    assert response_ids(responses, "Target") == ["a", "b"]

    assert response_ids([["Target", "not-a-dict", ""]], "Target") == []
    assert response_ids([["Target", {"ids": "nope"}, ""]], "Target") == []
    assert response_ids([], "Target") == []


# --------------------------------------------------------------------------- #
# response_created
# --------------------------------------------------------------------------- #


def test_response_created_variants() -> None:
    responses = [
        ["Short"],
        ["Other", {"created": {"a": {"id": "z"}}}, ""],
        ["Target", {"created": {"folder": {"id": "new-id"}}}, ""],
    ]
    assert response_created(responses, "Target") == {"id": "new-id"}

    assert response_created([["Target", "not-a-dict", ""]], "Target") == {}
    # created present but not a dict -> {}
    assert response_created([["Target", {"created": "nope"}, ""]], "Target") == {}
    # created dict but values not dicts -> {}
    assert response_created([["Target", {"created": {"a": "nope"}}, ""]], "Target") == {}
    assert response_created([], "Target") == {}


# --------------------------------------------------------------------------- #
# mailbox_id_by_role
# --------------------------------------------------------------------------- #


def test_mailbox_id_by_role_returns_id() -> None:
    def call(session, *, using, method_calls):
        return [["Mailbox/get", {"list": [{"id": "inbox-id", "role": "inbox"}]}, "mg0"]]

    assert mailbox_id_by_role(call, SESSION, "inbox") == "inbox-id"


def test_mailbox_id_by_role_not_found_raises() -> None:
    def call(session, *, using, method_calls):
        return [["Mailbox/get", {"list": []}, "mg0"]]

    with pytest.raises(ValueError, match="was not found"):
        mailbox_id_by_role(call, SESSION, "inbox")


def test_mailbox_id_by_role_missing_id_raises() -> None:
    def call(session, *, using, method_calls):
        return [["Mailbox/get", {"list": [{"role": "inbox"}]}, "mg0"]]

    with pytest.raises(ValueError, match="has no id"):
        mailbox_id_by_role(call, SESSION, "inbox")


# --------------------------------------------------------------------------- #
# ensure_mailbox
# --------------------------------------------------------------------------- #


def test_ensure_mailbox_returns_existing() -> None:
    def call(session, *, using, method_calls):
        return [["Mailbox/query", {"ids": ["existing-id"]}, ""]]

    assert ensure_mailbox(call, SESSION, "HeadStart/General") == "existing-id"


def test_ensure_mailbox_creates_when_absent() -> None:
    calls = []

    def call(session, *, using, method_calls):
        calls.append(method_calls[0][0])
        if method_calls[0][0] == "Mailbox/query":
            return [["Mailbox/query", {"ids": []}, ""]]
        return [["Mailbox/set", {"created": {"folder": {"id": "created-id"}}}, ""]]

    assert ensure_mailbox(call, SESSION, "HeadStart/New") == "created-id"
    assert calls == ["Mailbox/query", "Mailbox/set"]


def test_ensure_mailbox_creation_without_id_raises() -> None:
    def call(session, *, using, method_calls):
        if method_calls[0][0] == "Mailbox/query":
            return [["Mailbox/query", {"ids": []}, ""]]
        return [["Mailbox/set", {"created": {}}, ""]]

    with pytest.raises(ValueError, match="Could not create mailbox"):
        ensure_mailbox(call, SESSION, "HeadStart/New")
