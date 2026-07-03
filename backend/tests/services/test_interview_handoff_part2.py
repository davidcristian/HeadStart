"""Tests for interview handoff: active-application detection and classify path."""

from datetime import UTC, datetime
from unittest.mock import patch

from sqlalchemy.orm import Session

from app.core.config import settings
from app.email_classifiers import EmailClassificationResult, EmailClassifyContext
from app.inbox.types import InboxMessage
from app.models.application_log import ApplicationLog
from app.models.inbox_classification import InboxClassification
from app.models.notification_target import NotificationTarget
from app.models.seen_job import SeenJob
from app.notifiers.types import DeliveryResult
from app.schemas.inbox_classification import EmailClassifyRequest
from app.services.applications import derive_pipeline_stage, latest_live_attempt
from app.services.email_classification import EmailClassificationService
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


class StubClassifier:
    def __init__(self, label: str) -> None:
        self.label = label

    def classify(self, ctx: EmailClassifyContext) -> EmailClassificationResult:
        return EmailClassificationResult(
            label=self.label,
            confidence=0.9,
            reason="stub",
        )


def test_interview_handoff_active_via_submitted_log_when_not_applied(db_session: Session) -> None:
    # status "new" but a submitted live attempt exists -> active via the log path.
    search = _make_search(db_session)
    job = SeenJob(
        search_id=search.id,
        external_id="job-new-submitted",
        hash="h-new",
        title="Backend Engineer",
        company="ACME",
        location="Remote",
        url="https://careers.acme.com/jobs/2",
        status="new",
    )
    db_session.add(job)
    db_session.flush()
    db_session.add(ApplicationLog(seen_job_id=job.id, status="submitted", dry_run=False))
    db_session.flush()

    service = InterviewHandoffService(db_session)
    row = InboxClassification(
        user_id=search.user_id,
        seen_job_id=job.id,
        message_uid=11,
        label="interview_request",
        confidence=0.9,
        reason="stub",
        provider="heuristic",
        subject="Interview time?",
        from_addr="hr@careers.acme.com",
        payload={},
    )

    with patch.object(
        service.alerts,
        "notify_interview_handoff",
        return_value=[DeliveryResult(external_id=job.external_id, status="sent")],
    ):
        result = service.maybe_handoff_from_classification(search.user_id, job, row)

    assert result.handed_off is True
    assert job.interview_pending_at is not None


def test_interview_handoff_inactive_when_only_queued_log(db_session: Session) -> None:
    # status "new" with only a queued (not submitted) log -> not active, skipped.
    search = _make_search(db_session)
    job = SeenJob(
        search_id=search.id,
        external_id="job-queued",
        hash="h-queued",
        title="Backend Engineer",
        company="ACME",
        location="Remote",
        url="https://careers.acme.com/jobs/3",
        status="new",
    )
    db_session.add(job)
    db_session.flush()
    db_session.add(ApplicationLog(seen_job_id=job.id, status="queued", dry_run=False))
    db_session.flush()

    service = InterviewHandoffService(db_session)
    row = InboxClassification(
        user_id=search.user_id,
        seen_job_id=job.id,
        message_uid=12,
        label="interview_request",
        confidence=0.9,
        reason="stub",
        provider="heuristic",
        subject="Interview?",
        from_addr="hr@careers.acme.com",
        payload={},
    )

    with patch.object(service.alerts, "notify_interview_handoff") as notify:
        result = service.maybe_handoff_from_classification(search.user_id, job, row)

    assert result.handed_off is False
    notify.assert_not_called()


def test_classify_hands_off_interview_for_applied_job(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id, job = _seed_applied_job(db_session)
    db_session.add(
        NotificationTarget(user_id=user_id, name="ntfy", type="ntfy", config={"topic": "alerts"})
    )
    db_session.flush()

    service = EmailClassificationService(db_session)

    def factory(key: str, runtime: object) -> object:
        return StubClassifier("interview_request")

    service._factory = factory  # type: ignore[method-assign]

    with (
        patch.object(service, "_resolve_provider", return_value="heuristic"),
        patch("app.services.application_alerts.get_notifier") as get_notifier,
    ):
        notifier = get_notifier.return_value
        notifier.send.return_value = [DeliveryResult(external_id=job.external_id, status="sent")]
        result = service.classify(
            user_id,
            EmailClassifyRequest(
                message=InboxMessage(
                    uid=42,
                    from_addr="hr@careers.acme.com",
                    subject="Calendly invite for Backend Engineer",
                    body_text="Please pick a time for your phone screen.",
                )
            ),
        )

    assert result.label == "interview_request"
    db_session.refresh(job)
    assert job.interview_pending_at is not None
    latest = latest_live_attempt(job.application_logs)
    assert derive_pipeline_stage(job, latest) == "interview_pending"
    get_notifier.assert_called_once()
