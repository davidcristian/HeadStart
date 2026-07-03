"""Tests for ghost summary email composition."""

from datetime import UTC, datetime

from app.email_classifiers.labels import GHOST_HEADER_TYPE, GHOST_HEADER_VALUE, GHOST_SUBJECT_PREFIX
from app.inbox.ghost_message import build_ghost_summary_message, mailbox_self_address
from app.models.seen_job import SeenJob


def test_mailbox_self_address_prefers_smtp_from() -> None:
    assert (
        mailbox_self_address(imap_user="imap@example.test", smtp_from="from@example.test")
        == "from@example.test"
    )
    assert mailbox_self_address(imap_user="imap@example.test", smtp_from="") == "imap@example.test"


def test_build_ghost_summary_message_includes_markers() -> None:
    job = SeenJob(
        id=42,
        search_id=1,
        external_id="ext-1",
        hash="h1",
        title="Backend Engineer",
        company="ACME",
        location="Remote",
        url="https://example.test/jobs/1",
        status="applied",
        applied_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
    )
    message = build_ghost_summary_message(job=job, mailbox_email="user@example.test")

    assert message.to == ["user@example.test"]
    assert message.subject.startswith(GHOST_SUBJECT_PREFIX)
    assert "ACME" in message.subject
    assert "Backend Engineer" in message.subject
    assert message.extra_headers[GHOST_HEADER_TYPE] == GHOST_HEADER_VALUE
    assert message.extra_headers["X-HeadStart-Job-Id"] == "42"
    assert "https://example.test/jobs/1" in message.body
