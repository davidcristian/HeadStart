"""Branch coverage for ghost self-archive detection and body formatting."""

from datetime import UTC, datetime

from app.email_classifiers.labels import (
    GHOST_HEADER_TYPE,
    GHOST_HEADER_VALUE,
    GHOST_SUBJECT_PREFIX,
)
from app.inbox.ghost_message import (
    build_ghost_summary_message,
    is_self_ghost_archive_message,
)
from app.inbox.types import InboxMessage
from app.models.seen_job import SeenJob


def _msg(**kwargs) -> InboxMessage:
    return InboxMessage(uid=1, **kwargs)


def test_detects_ghost_header() -> None:
    msg = _msg(raw_headers={GHOST_HEADER_TYPE: GHOST_HEADER_VALUE})
    assert is_self_ghost_archive_message(msg, "user@example.test") is True


def test_detects_ghost_subject_prefix() -> None:
    msg = _msg(subject=f"{GHOST_SUBJECT_PREFIX} No reply: ACME")
    assert is_self_ghost_archive_message(msg, "user@example.test") is True


def test_detects_self_from_and_to_match() -> None:
    msg = _msg(from_addr="User@Example.test", to_addrs=["user@example.TEST"])
    assert is_self_ghost_archive_message(msg, "user@example.test") is True


def test_returns_false_when_mailbox_blank() -> None:
    msg = _msg(from_addr="a@b.test", to_addrs=["a@b.test"])
    assert is_self_ghost_archive_message(msg, "   ") is False


def test_returns_false_when_no_markers_match() -> None:
    msg = _msg(from_addr="hr@company.test", to_addrs=["user@example.test"], subject="Hello")
    assert is_self_ghost_archive_message(msg, "user@example.test") is False


def test_build_ghost_summary_without_url_omits_job_link() -> None:
    job = SeenJob(
        id=7,
        search_id=1,
        external_id="ext",
        hash="h",
        title="",
        company="",
        location="",
        url="",
        status="applied",
        applied_at=None,
    )
    message = build_ghost_summary_message(job=job, mailbox_email="user@example.test")
    assert "Job link:" not in message.body
    assert "Unknown company" in message.subject
    assert "Unknown role" in message.subject
    assert "Applied: unknown" in message.body


def test_build_ghost_summary_with_applied_at() -> None:
    job = SeenJob(
        id=8,
        search_id=1,
        external_id="ext",
        hash="h",
        title="Engineer",
        company="ACME",
        location="Remote",
        url="https://x.test/1",
        status="applied",
        applied_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    message = build_ghost_summary_message(job=job, mailbox_email="user@example.test")
    assert "Job link: https://x.test/1" in message.body
