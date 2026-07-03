"""Tests for interview handoff when recruiter mail requests scheduling."""

from datetime import UTC, datetime
from unittest.mock import patch

from sqlalchemy.orm import Session

from app.models.application_log import ApplicationLog
from app.models.inbox_classification import InboxClassification
from app.models.seen_job import SeenJob
from app.notifiers.types import DeliveryResult
from app.services.interview_handoff import InterviewHandoffService
from tests.worker.test_pipeline import _make_search


def _seed_applied_job(session: Session) -> tuple[int, SeenJob]:
    search = _make_search(session)
    job = SeenJob(
        search_id=search.id,
        external_id="job-applied",
        hash="h-applied",
        title="Backend Engineer",
        company="ACME",
        location="Remote",
        url="https://careers.acme.com/jobs/1",
        status="applied",
        applied_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
    )
    session.add(job)
    session.flush()
    session.add(
        ApplicationLog(
            seen_job_id=job.id,
            status="submitted",
            dry_run=False,
            payload={"employer_domain": "careers.acme.com"},
        )
    )
    session.flush()
    return search.user_id, job


def test_interview_handoff_sets_pending_and_alerts(db_session: Session) -> None:
    user_id, job = _seed_applied_job(db_session)
    service = InterviewHandoffService(db_session)
    row = InboxClassification(
        user_id=user_id,
        seen_job_id=job.id,
        message_uid=1,
        label="interview_request",
        confidence=0.9,
        reason="stub",
        provider="heuristic",
        subject="Schedule a phone screen",
        from_addr="hr@careers.acme.com",
        payload={},
    )

    with patch.object(
        service.alerts,
        "notify_interview_handoff",
        return_value=[DeliveryResult(external_id=job.external_id, status="sent")],
    ) as notify:
        result = service.maybe_handoff_from_classification(user_id, job, row)

    assert result.handed_off is True
    assert job.interview_pending_at is not None
    assert row.payload["interview_handoff"]["handed_off_at"] is not None
    notify.assert_called_once_with(
        user_id,
        job,
        email_subject="Schedule a phone screen",
    )


def test_interview_handoff_skips_non_interview_labels(db_session: Session) -> None:
    user_id, job = _seed_applied_job(db_session)
    service = InterviewHandoffService(db_session)
    row = InboxClassification(
        user_id=user_id,
        seen_job_id=job.id,
        message_uid=2,
        label="follow_up",
        confidence=0.9,
        reason="stub",
        provider="heuristic",
        subject="Quick question",
        from_addr="hr@careers.acme.com",
        payload={},
    )

    result = service.maybe_handoff_from_classification(user_id, job, row)

    assert result.handed_off is False
    assert job.interview_pending_at is None


def test_interview_handoff_skips_ghosted_jobs(db_session: Session) -> None:
    user_id, job = _seed_applied_job(db_session)
    job.ghosted_at = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    service = InterviewHandoffService(db_session)
    row = InboxClassification(
        user_id=user_id,
        seen_job_id=job.id,
        message_uid=3,
        label="interview_request",
        confidence=0.9,
        reason="stub",
        provider="heuristic",
        subject="Schedule a call",
        from_addr="hr@careers.acme.com",
        payload={},
    )

    with patch.object(service.alerts, "notify_interview_handoff") as notify:
        result = service.maybe_handoff_from_classification(user_id, job, row)

    assert result.handed_off is False
    assert job.interview_pending_at is None
    notify.assert_not_called()


def test_interview_handoff_skips_when_already_pending(db_session: Session) -> None:
    user_id, job = _seed_applied_job(db_session)
    job.interview_pending_at = datetime(2026, 6, 25, 12, 0, tzinfo=UTC)
    service = InterviewHandoffService(db_session)
    row = InboxClassification(
        user_id=user_id,
        seen_job_id=job.id,
        message_uid=4,
        label="interview_request",
        confidence=0.9,
        reason="stub",
        provider="heuristic",
        subject="Another scheduling link",
        from_addr="hr@careers.acme.com",
        payload={},
    )

    with patch.object(service.alerts, "notify_interview_handoff") as notify:
        result = service.maybe_handoff_from_classification(user_id, job, row)

    assert result.handed_off is False
    notify.assert_not_called()


def test_interview_handoff_skips_inactive_application(db_session: Session) -> None:
    user_id, job = _seed_applied_job(db_session)
    # A closed job is not an active application, so handoff is skipped.
    job.status = "closed"
    db_session.flush()
    service = InterviewHandoffService(db_session)
    row = InboxClassification(
        user_id=user_id,
        seen_job_id=job.id,
        message_uid=10,
        label="interview_request",
        confidence=0.9,
        reason="stub",
        provider="heuristic",
        subject="Schedule a chat",
        from_addr="hr@careers.acme.com",
        payload={},
    )

    with patch.object(service.alerts, "notify_interview_handoff") as notify:
        result = service.maybe_handoff_from_classification(user_id, job, row)

    assert result.handed_off is False
    assert job.interview_pending_at is None
    notify.assert_not_called()
