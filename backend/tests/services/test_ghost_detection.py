"""Tests for ghost detection on stale applications."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from app.core.config import settings
from app.inbox.types import SendResult
from app.models.application_log import ApplicationLog
from app.models.seen_job import SeenJob
from app.models.user import User
from app.schemas.mailbox import MailboxConfig, MailboxCredentialUpsert
from app.services.ghost_detection import GhostDetectionService
from app.services.inbox import InboxService
from tests.worker.pipeline_helpers import make_search as _make_search


def _user(session: Session, email: str = "ghost@example.test") -> int:
    user = User(email=email, password_hash="x", is_admin=False, is_active=True, plan="pro")
    session.add(user)
    session.flush()
    return user.id


def _mailbox_config() -> MailboxConfig:
    return MailboxConfig(
        imap_host="imap.example.com",
        imap_user="user@example.com",
        imap_password="imap-pass",
        smtp_host="smtp.example.com",
        smtp_password="smtp-pass",
        smtp_from="user@example.com",
    )


def _applied_job(
    session: Session,
    *,
    user_id: int,
    applied_at: datetime,
    ghosted_at: datetime | None = None,
    external_id: str = "job-ghost-1",
    job_hash: str = "h-ghost",
) -> SeenJob:
    user = session.get(User, user_id)
    assert user is not None
    search = _make_search(session, user=user)
    job = SeenJob(
        search_id=search.id,
        external_id=external_id,
        hash=job_hash,
        title="Platform Engineer",
        company="GhostCo",
        location="Remote",
        url=f"https://example.test/jobs/{external_id}",
        status="applied",
        applied_at=applied_at,
        ghosted_at=ghosted_at,
    )
    session.add(job)
    session.flush()
    session.add(
        ApplicationLog(
            seen_job_id=job.id,
            status="submitted",
            dry_run=False,
            external_application_id=f"ext-{external_id}",
        )
    )
    session.flush()
    return job


def test_process_due_disabled_when_inbox_agent_off(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", False)
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    result = GhostDetectionService(db_session).process_due(now=now)
    assert result.checked == 0
    assert result.ghosted == 0


def test_process_due_ghosts_stale_application(
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_ghost_window_days", 14)
    user_id = _user(db_session)
    InboxService(db_session).upsert(
        user_id,
        MailboxCredentialUpsert(config=_mailbox_config()),
    )
    applied_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    job = _applied_job(db_session, user_id=user_id, applied_at=applied_at)

    send_mock = MagicMock(return_value=SendResult(status="sent"))
    monkeypatch.setattr(InboxService, "send_message", send_mock)

    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    result = GhostDetectionService(db_session).process_due(now=now)

    assert result.checked == 1
    assert result.ghosted == 1
    assert job.ghosted_at == now
    send_mock.assert_called_once()
    message = send_mock.call_args.args[1]
    assert message.to == ["user@example.com"]
    assert message.subject.startswith("[HeadStart Ghost]")


def test_process_due_skips_recent_application(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_ghost_window_days", 14)
    user_id = _user(db_session)
    InboxService(db_session).upsert(
        user_id,
        MailboxCredentialUpsert(config=_mailbox_config()),
    )
    applied_at = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    _applied_job(db_session, user_id=user_id, applied_at=applied_at)

    send_mock = MagicMock(return_value=SendResult(status="sent"))
    monkeypatch.setattr(InboxService, "send_message", send_mock)

    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    result = GhostDetectionService(db_session).process_due(now=now)

    assert result.checked == 0
    assert result.ghosted == 0
    send_mock.assert_not_called()


def test_process_due_does_not_mark_when_send_fails(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_ghost_window_days", 1)
    user_id = _user(db_session)
    InboxService(db_session).upsert(
        user_id,
        MailboxCredentialUpsert(config=_mailbox_config()),
    )
    applied_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    job = _applied_job(db_session, user_id=user_id, applied_at=applied_at)

    send_mock = MagicMock(return_value=SendResult(status="failed", error="smtp down"))
    monkeypatch.setattr(InboxService, "send_message", send_mock)

    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    result = GhostDetectionService(db_session).process_due(now=now)

    assert result.failed == 1
    assert result.ghosted == 0
    assert job.ghosted_at is None


def test_process_due_skips_without_mailbox(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_ghost_window_days", 1)
    user_id = _user(db_session)
    applied_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    job = _applied_job(db_session, user_id=user_id, applied_at=applied_at)

    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    result = GhostDetectionService(db_session).process_due(now=now)

    assert result.checked == 1
    assert result.skipped == 1
    assert job.ghosted_at is None


def test_process_due_skips_when_mailbox_email_empty(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_ghost_window_days", 1)
    user_id = _user(db_session)
    InboxService(db_session).upsert(
        user_id,
        MailboxCredentialUpsert(config=_mailbox_config()),
    )
    applied_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    job = _applied_job(db_session, user_id=user_id, applied_at=applied_at)

    # Context resolves, but the derived mailbox address is blank -> skip.
    monkeypatch.setattr(
        "app.services.ghost_detection.mailbox_email_from_context",
        lambda ctx: "",
    )
    send_mock = MagicMock(return_value=SendResult(status="sent"))
    monkeypatch.setattr(InboxService, "send_message", send_mock)

    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    result = GhostDetectionService(db_session).process_due(now=now)

    assert result.checked == 1
    assert result.skipped == 1
    assert job.ghosted_at is None
    send_mock.assert_not_called()


def test_process_due_skips_failed_apply(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_ghost_window_days", 1)
    user_id = _user(db_session)
    InboxService(db_session).upsert(
        user_id,
        MailboxCredentialUpsert(config=_mailbox_config()),
    )
    user = db_session.get(User, user_id)
    assert user is not None
    search = _make_search(db_session, user=user)
    job = SeenJob(
        search_id=search.id,
        external_id="job-fail",
        hash="h-fail",
        title="Role",
        company="Co",
        url="https://example.test/jobs/fail",
        status="applied",
        applied_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
    )
    db_session.add(job)
    db_session.flush()
    db_session.add(
        ApplicationLog(
            seen_job_id=job.id,
            status="failed",
            dry_run=False,
            error="timeout",
        )
    )
    db_session.flush()

    send_mock = MagicMock(return_value=SendResult(status="sent"))
    monkeypatch.setattr(InboxService, "send_message", send_mock)

    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    result = GhostDetectionService(db_session).process_due(now=now)

    assert result.skipped == 1
    assert result.ghosted == 0
    send_mock.assert_not_called()


def test_process_due_isolates_per_job_exception(db_session: Session, monkeypatch) -> None:
    """One job raise must not abort the rest of the batch (SVC-06)."""
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_ghost_window_days", 1)
    first_user = _user(db_session, email="ghost-fail@example.test")
    second_user = _user(db_session, email="ghost-ok@example.test")
    for uid in (first_user, second_user):
        InboxService(db_session).upsert(
            uid,
            MailboxCredentialUpsert(config=_mailbox_config()),
        )
    applied_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    failing = _applied_job(
        db_session,
        user_id=first_user,
        applied_at=applied_at,
        external_id="job-fail-raise",
        job_hash="h-fail-raise",
    )
    succeeding = _applied_job(
        db_session,
        user_id=second_user,
        applied_at=applied_at,
        external_id="job-ok",
        job_hash="h-ok",
    )
    assert failing.id < succeeding.id
    db_session.commit()

    def _send(self: InboxService, user_id: int, message: object) -> SendResult:
        if user_id == first_user:
            raise RuntimeError("token refresh blew up")
        return SendResult(status="sent")

    monkeypatch.setattr(InboxService, "send_message", _send)

    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    result = GhostDetectionService(db_session).process_due(now=now)

    assert result.checked == 2
    assert result.failed == 1
    assert result.ghosted == 1
    db_session.expire_all()
    refreshed_fail = db_session.get(SeenJob, failing.id)
    refreshed_ok = db_session.get(SeenJob, succeeding.id)
    assert refreshed_fail is not None and refreshed_fail.ghosted_at is None
    assert refreshed_ok is not None
    assert refreshed_ok.ghosted_at is not None
    assert refreshed_ok.ghosted_at.replace(tzinfo=UTC) == now


def test_process_due_commits_before_later_job_failure(db_session: Session, monkeypatch) -> None:
    """A later raise must not roll back an earlier successful ghost (SVC-06)."""
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_ghost_window_days", 1)
    first_user = _user(db_session, email="ghost-first@example.test")
    second_user = _user(db_session, email="ghost-second@example.test")
    for uid in (first_user, second_user):
        InboxService(db_session).upsert(
            uid,
            MailboxCredentialUpsert(config=_mailbox_config()),
        )
    applied_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    first = _applied_job(
        db_session,
        user_id=first_user,
        applied_at=applied_at,
        external_id="job-first",
        job_hash="h-first",
    )
    second = _applied_job(
        db_session,
        user_id=second_user,
        applied_at=applied_at,
        external_id="job-second",
        job_hash="h-second",
    )
    assert first.id < second.id
    db_session.commit()

    def _send(self: InboxService, user_id: int, message: object) -> SendResult:
        if user_id == second_user:
            raise RuntimeError("smtp blew up")
        return SendResult(status="sent")

    monkeypatch.setattr(InboxService, "send_message", _send)

    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    result = GhostDetectionService(db_session).process_due(now=now)

    assert result.checked == 2
    assert result.ghosted == 1
    assert result.failed == 1
    db_session.expire_all()
    refreshed_first = db_session.get(SeenJob, first.id)
    refreshed_second = db_session.get(SeenJob, second.id)
    assert refreshed_first is not None and refreshed_first.ghosted_at is not None
    assert refreshed_first.ghosted_at.replace(tzinfo=UTC) == now
    assert refreshed_second is not None and refreshed_second.ghosted_at is None
