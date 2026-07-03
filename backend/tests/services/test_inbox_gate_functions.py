"""Unit tests for inbox gate pure helper functions."""

from app.inbox.types import InboxMessage
from app.models.application_log import ApplicationLog
from app.models.seen_job import SeenJob
from app.services.inbox_gate import (
    email_domain_from_job_url,
    message_references_outbound,
    normalize_message_id,
    outbound_message_ids_from_log,
    parse_referenced_message_ids,
    sender_matches_employer_domain,
    sender_on_allowlist,
)


def test_email_domain_from_job_url_strips_www() -> None:
    job = SeenJob(
        search_id=1,
        external_id="x",
        hash="x",
        title="t",
        company="c",
        location="l",
        url="https://www.Careers.Acme.com/jobs/1",
        status="applied",
    )
    assert email_domain_from_job_url(job) == "careers.acme.com"


def test_email_domain_from_job_url_empty_when_no_host() -> None:
    job = SeenJob(
        search_id=1,
        external_id="x",
        hash="x",
        title="t",
        company="c",
        location="l",
        url="mailto:someone",
        status="applied",
    )
    assert email_domain_from_job_url(job) == ""


def test_outbound_message_ids_from_log_variants() -> None:
    assert outbound_message_ids_from_log(None) == set()
    empty_log = ApplicationLog(seen_job_id=1, status="submitted", dry_run=False, payload={})
    assert outbound_message_ids_from_log(empty_log) == set()
    not_list = ApplicationLog(
        seen_job_id=1,
        status="submitted",
        dry_run=False,
        payload={"outbound_message_ids": "<single@x>"},
    )
    assert outbound_message_ids_from_log(not_list) == set()
    good = ApplicationLog(
        seen_job_id=1,
        status="submitted",
        dry_run=False,
        payload={"outbound_message_ids": ["<a@x>", "  ", "<b@x>"]},
    )
    assert outbound_message_ids_from_log(good) == {"<a@x>", "<b@x>"}


def test_normalize_message_id_trims() -> None:
    assert normalize_message_id("  <a@x>  ") == "<a@x>"


def test_parse_referenced_message_ids_tokens_and_whitespace() -> None:
    assert parse_referenced_message_ids("<a@x> <b@x>") == ["<a@x>", "<b@x>"]
    assert parse_referenced_message_ids("plain1 plain2") == ["plain1", "plain2"]


def test_message_references_outbound_via_references_header() -> None:
    outbound = frozenset({"<root@headstart.local>"})
    message = InboxMessage(
        uid=1,
        references="<middle@x> <root@headstart.local>",
        subject="Re",
        body_text="body",
    )
    assert message_references_outbound(message, outbound) is True


def test_message_references_outbound_no_match_returns_false() -> None:
    outbound = frozenset({"<root@headstart.local>"})
    message = InboxMessage(
        uid=1,
        in_reply_to="<other@x>",
        references="<unrelated@x>",
        subject="Re",
        body_text="body",
    )
    assert message_references_outbound(message, outbound) is False


def test_message_references_outbound_empty_outbound() -> None:
    message = InboxMessage(uid=1, in_reply_to="<a@x>", subject="Re", body_text="body")
    assert message_references_outbound(message, frozenset()) is False


def test_sender_on_allowlist_empty_and_present() -> None:
    assert sender_on_allowlist("a@x.com", frozenset()) is False
    assert sender_on_allowlist(" A@X.com ", frozenset({"a@x.com"})) is True


def test_sender_matches_employer_domain_empty_inputs() -> None:
    assert sender_matches_employer_domain("no-at-sign", frozenset({"acme.com"})) is False
    assert sender_matches_employer_domain("a@acme.com", frozenset()) is False
