"""Tests for application pipeline aggregation."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.application_log import ApplicationLog
from app.models.inbox_classification import InboxClassification
from app.models.inbox_reply_draft import InboxReplyDraft
from app.models.seen_job import SeenJob
from app.services.applications import (
    ApplicationPipelineService,
    derive_pipeline_stage,
    latest_live_attempt,
)
from tests.worker.test_pipeline import _make_search


def _seed_job(session: Session) -> tuple[int, SeenJob]:
    search = _make_search(session)
    job = SeenJob(
        search_id=search.id,
        external_id="job-1",
        hash="h1",
        title="Backend Engineer",
        company="ACME",
        location="Remote",
        url="https://example.test/jobs/1",
        status="new",
    )
    session.add(job)
    session.flush()
    return search.user_id, job


def test_derive_pipeline_stage_awaiting_reply_after_submit(db_session: Session) -> None:
    """Applied + submitted share the default awaiting_reply fall-through."""
    _, job = _seed_job(db_session)
    log = ApplicationLog(
        seen_job_id=job.id,
        status="submitted",
        dry_run=False,
        external_application_id="ext-1",
    )
    job.status = "applied"
    job.applied_at = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    db_session.add(log)
    db_session.flush()

    assert derive_pipeline_stage(job, log) == "awaiting_reply"


def test_derive_pipeline_stage_submitted_without_applied_status(
    db_session: Session,
) -> None:
    """Live submitted attempt alone still maps to awaiting_reply (no distinct stage)."""
    _, job = _seed_job(db_session)
    log = ApplicationLog(
        seen_job_id=job.id,
        status="submitted",
        dry_run=False,
        external_application_id="ext-2",
    )
    db_session.add(log)
    db_session.flush()

    assert job.status == "new"
    assert derive_pipeline_stage(job, log) == "awaiting_reply"


def test_derive_pipeline_stage_ghosted(db_session: Session) -> None:
    _, job = _seed_job(db_session)
    job.status = "applied"
    job.applied_at = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    job.ghosted_at = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    db_session.flush()

    assert derive_pipeline_stage(job, None) == "ghosted"


def test_derive_pipeline_stage_interview_pending(db_session: Session) -> None:
    _, job = _seed_job(db_session)
    job.status = "applied"
    job.applied_at = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    job.interview_pending_at = datetime(2026, 6, 30, 14, 0, tzinfo=UTC)
    db_session.flush()

    assert derive_pipeline_stage(job, None) == "interview_pending"


def test_derive_pipeline_stage_rejected(db_session: Session) -> None:
    _, job = _seed_job(db_session)
    job.status = "applied"
    job.applied_at = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    job.recruiter_rejection_at = datetime(2026, 6, 30, 14, 0, tzinfo=UTC)
    db_session.flush()

    assert derive_pipeline_stage(job, None) == "rejected"


def test_derive_pipeline_stage_recovered_not_ghosted(db_session: Session) -> None:
    _, job = _seed_job(db_session)
    job.status = "applied"
    job.applied_at = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    job.ghost_recovered_at = datetime(2026, 6, 30, 14, 0, tzinfo=UTC)
    db_session.flush()

    assert derive_pipeline_stage(job, None) == "awaiting_reply"


def test_pipeline_service_filters_ghosted_stage(db_session: Session) -> None:
    user_id, job = _seed_job(db_session)
    job.status = "applied"
    job.applied_at = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    job.ghosted_at = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    db_session.add(
        ApplicationLog(
            seen_job_id=job.id,
            status="submitted",
            dry_run=False,
        )
    )
    db_session.flush()

    ghosted = ApplicationPipelineService(db_session).list_for_user(user_id, stage="ghosted")
    awaiting = ApplicationPipelineService(db_session).list_for_user(user_id, stage="awaiting_reply")
    assert len(ghosted) == 1
    assert ghosted[0].pipeline_stage == "ghosted"
    assert ghosted[0].ghosted_at is not None
    assert awaiting == []


def test_derive_pipeline_stage_apply_failed(db_session: Session) -> None:
    _, job = _seed_job(db_session)
    log = ApplicationLog(
        seen_job_id=job.id,
        status="failed",
        dry_run=False,
        error="timeout",
    )
    db_session.add(log)
    db_session.flush()

    assert derive_pipeline_stage(job, log) == "apply_failed"


def test_latest_live_attempt_ignores_dry_run(db_session: Session) -> None:
    _, job = _seed_job(db_session)
    preview = ApplicationLog(
        seen_job_id=job.id,
        status="dry_run",
        dry_run=True,
        created_at=datetime(2026, 6, 28, 11, 0, tzinfo=UTC),
    )
    live = ApplicationLog(
        seen_job_id=job.id,
        status="submitted",
        dry_run=False,
        created_at=datetime(2026, 6, 28, 12, 0, tzinfo=UTC),
    )
    db_session.add_all([preview, live])
    db_session.flush()

    assert latest_live_attempt([preview, live]) == live


def test_pipeline_service_lists_applied_jobs(db_session: Session) -> None:
    user_id, job = _seed_job(db_session)
    job.status = "applied"
    job.applied_at = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    db_session.add(
        ApplicationLog(
            seen_job_id=job.id,
            status="submitted",
            dry_run=False,
            external_application_id="ext-42",
        )
    )
    db_session.flush()

    rows = ApplicationPipelineService(db_session).list_for_user(user_id)
    assert len(rows) == 1
    assert rows[0].job_id == job.id
    assert rows[0].pipeline_stage == "awaiting_reply"
    assert rows[0].latest_attempt is not None
    assert rows[0].latest_attempt.external_application_id == "ext-42"
    assert len(rows[0].attempts) == 1


def test_pipeline_service_filters_by_stage(db_session: Session) -> None:
    user_id, job = _seed_job(db_session)
    db_session.add(
        ApplicationLog(
            seen_job_id=job.id,
            status="failed",
            dry_run=False,
            error="network",
        )
    )
    db_session.flush()

    failed = ApplicationPipelineService(db_session).list_for_user(user_id, stage="apply_failed")
    awaiting = ApplicationPipelineService(db_session).list_for_user(user_id, stage="awaiting_reply")
    assert len(failed) == 1
    assert failed[0].pipeline_stage == "apply_failed"
    assert awaiting == []


def test_derive_pipeline_stage_closed(db_session: Session) -> None:
    _, job = _seed_job(db_session)
    job.status = "closed"
    db_session.flush()
    assert derive_pipeline_stage(job, None) == "closed"


def test_derive_pipeline_stage_archived(db_session: Session) -> None:
    _, job = _seed_job(db_session)
    job.status = "archived"
    db_session.flush()
    assert derive_pipeline_stage(job, None) == "archived"


def test_derive_pipeline_stage_queued(db_session: Session) -> None:
    _, job = _seed_job(db_session)
    log = ApplicationLog(seen_job_id=job.id, status="queued", dry_run=False)
    db_session.add(log)
    db_session.flush()
    assert derive_pipeline_stage(job, log) == "queued"


def test_derive_pipeline_stage_defaults_to_awaiting_reply(db_session: Session) -> None:
    _, job = _seed_job(db_session)
    db_session.flush()
    # status "new", no live attempt -> the fall-through default.
    assert derive_pipeline_stage(job, None) == "awaiting_reply"


def test_pipeline_row_includes_latest_reply_draft_and_classification(db_session: Session) -> None:
    user_id, job = _seed_job(db_session)
    job.status = "applied"
    job.applied_at = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    db_session.add(ApplicationLog(seen_job_id=job.id, status="submitted", dry_run=False))
    classification = InboxClassification(
        user_id=user_id,
        seen_job_id=job.id,
        message_uid=1,
        label="follow_up",
        confidence=0.9,
        reason="stub",
        provider="heuristic",
        subject="Re: your application",
        from_addr="hr@acme.test",
        payload={},
    )
    db_session.add(classification)
    db_session.flush()
    draft = InboxReplyDraft(
        user_id=user_id,
        seen_job_id=job.id,
        inbox_classification_id=classification.id,
        message_uid=1,
        subject="Re: your application",
        body_text="Thanks for reaching out.",
        provider="heuristic",
    )
    db_session.add(draft)
    db_session.flush()

    rows = ApplicationPipelineService(db_session).list_for_user(user_id)
    assert len(rows) == 1
    row = rows[0]
    assert row.latest_reply_draft is not None
    assert row.latest_reply_draft.subject == "Re: your application"
    assert row.latest_draftable_classification_id == classification.id


def test_draft_and_classification_helpers_ignore_wrong_types(db_session: Session) -> None:
    service = ApplicationPipelineService(db_session)
    # None short-circuits, and a non-model object hits the defensive isinstance guard.
    assert service._draft_summary(None) is None
    assert service._draft_summary(object()) is None
    assert service._classification_id(object()) is None


def test_attempt_summary_none_for_no_attempts(db_session: Session) -> None:
    user_id, job = _seed_job(db_session)
    job.status = "applied"
    db_session.flush()
    # Applied status with no live application logs -> latest attempt is None.
    rows = ApplicationPipelineService(db_session).list_for_user(user_id)
    assert len(rows) == 1
    assert rows[0].latest_attempt is None
    assert rows[0].attempts == []
