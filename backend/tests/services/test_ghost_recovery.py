"""Tests for ghost recovery when recruiter mail arrives."""

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
from app.services.email_classification import EmailClassificationService
from app.services.ghost_recovery import GhostRecoveryService
from tests.worker.test_pipeline import _make_search


def _seed_ghosted_job(session: Session) -> tuple[int, SeenJob]:
    search = _make_search(session)
    job = SeenJob(
        search_id=search.id,
        external_id="job-ghost",
        hash="h-ghost",
        title="Backend Engineer",
        company="ACME",
        location="Remote",
        url="https://careers.acme.com/jobs/1",
        status="applied",
        applied_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
        ghosted_at=datetime(2026, 6, 20, 12, 0, tzinfo=UTC),
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


def test_ghost_recovery_clears_ghost_and_sets_interview_pending(db_session: Session) -> None:
    user_id, job = _seed_ghosted_job(db_session)
    service = GhostRecoveryService(db_session)
    row = InboxClassification(
        user_id=user_id,
        seen_job_id=job.id,
        message_uid=1,
        label="interview_request",
        confidence=0.9,
        reason="stub",
        provider="heuristic",
        subject="Schedule a call",
        from_addr="hr@careers.acme.com",
        payload={},
    )

    with patch.object(
        service.alerts,
        "notify_ghost_recovery",
        return_value=[DeliveryResult(external_id=job.external_id, status="sent")],
    ) as notify:
        result = service.maybe_recover_from_classification(user_id, job, row)

    assert result.recovered is True
    assert result.pipeline_stage == "interview_pending"
    assert job.ghosted_at is None
    assert job.ghost_recovered_at is not None
    assert job.interview_pending_at is not None
    assert row.payload["ghost_recovery"]["pipeline_stage"] == "interview_pending"
    notify.assert_called_once()


def test_ghost_recovery_ignored_for_non_signal_labels(db_session: Session) -> None:
    user_id, job = _seed_ghosted_job(db_session)
    service = GhostRecoveryService(db_session)
    row = InboxClassification(
        user_id=user_id,
        seen_job_id=job.id,
        message_uid=2,
        label="out_of_scope",
        confidence=0.9,
        reason="stub",
        provider="heuristic",
        subject="Pancake recipe",
        from_addr="spam@example.com",
        payload={},
    )

    result = service.maybe_recover_from_classification(user_id, job, row)

    assert result.recovered is False
    assert job.ghosted_at is not None
    assert job.ghost_recovered_at is None


def test_classify_recovers_ghosted_job_and_moves_stage(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id, job = _seed_ghosted_job(db_session)
    db_session.add(
        NotificationTarget(user_id=user_id, name="ntfy", type="ntfy", config={"topic": "alerts"})
    )
    db_session.flush()

    service = EmailClassificationService(db_session)

    def factory(key: str, runtime: object) -> object:
        return StubClassifier("follow_up")

    service._factory = factory  # type: ignore[method-assign]

    with (
        patch.object(service, "_resolve_provider", return_value="heuristic"),
        patch(
            "app.services.application_alerts.get_notifier",
        ) as get_notifier,
    ):
        notifier = get_notifier.return_value
        notifier.send.return_value = [DeliveryResult(external_id=job.external_id, status="sent")]
        result = service.classify(
            user_id,
            EmailClassifyRequest(
                message=InboxMessage(
                    uid=99,
                    from_addr="hr@careers.acme.com",
                    subject="Following up on your application",
                    body_text="Do you have time for a quick chat?",
                )
            ),
        )

    assert result.label == "follow_up"
    db_session.refresh(job)
    assert job.ghosted_at is None
    assert job.ghost_recovered_at is not None
    assert job.interview_pending_at is None

    from app.services.applications import derive_pipeline_stage, latest_live_attempt

    assert derive_pipeline_stage(job, latest_live_attempt(job.application_logs)) == "awaiting_reply"

    ghosted = [row for row in service.pipeline.list_jobs_for_user(user_id) if row.id == job.id]
    assert ghosted[0].ghosted_at is None
