"""Service tests for inbox reply drafting."""

from datetime import UTC, datetime
from unittest.mock import patch

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.inbox.types import InboxMessage
from app.models.application_log import ApplicationLog
from app.models.inbox_classification import InboxClassification
from app.models.seen_job import SeenJob
from app.reply_drafters.types import ReplyDraftContext, ReplyDraftResult
from app.schemas.inbox_classification import EmailClassifyRequest
from app.schemas.inbox_reply_draft import ReplyDraftRequest
from app.schemas.profile import ProfileData
from app.services.email_classification import EmailClassificationService
from app.services.profiles import ProfileService
from app.services.reply_drafts import ReplyDraftService
from tests.worker.test_pipeline import _make_search


def _seed_applied_job(session: Session) -> tuple[int, SeenJob]:
    search = _make_search(session)
    job = SeenJob(
        search_id=search.id,
        external_id="job-1",
        hash="h1",
        title="Backend Engineer",
        company="ACME",
        location="Remote",
        url="https://careers.acme.com/jobs/1",
        status="applied",
        applied_at=datetime(2026, 6, 28, 12, 0, tzinfo=UTC),
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


def _classify_follow_up(session: Session, user_id: int) -> InboxClassification:
    monkeypatch_enabled = settings.inbox_agent_enabled
    settings.inbox_agent_enabled = True
    try:
        service = EmailClassificationService(session)
        with patch.object(service, "_resolve_provider", return_value="heuristic"):
            result = service.classify(
                user_id,
                EmailClassifyRequest(
                    message=InboxMessage(
                        uid=99,
                        from_addr="hr@careers.acme.com",
                        subject="Quick question",
                        body_text="What are your salary expectations?",
                    )
                ),
            )
    finally:
        settings.inbox_agent_enabled = monkeypatch_enabled
    row = service.classifications.get_by_id_for_user(user_id, result.id)
    assert row is not None
    return row


class StubDrafter:
    def draft(self, ctx: ReplyDraftContext) -> ReplyDraftResult:
        return ReplyDraftResult(
            subject="Re: Quick question",
            body="Thanks for reaching out. My salary expectations are competitive.",
            notes="stub",
        )


def test_draft_persists_heuristic_reply(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id, _job = _seed_applied_job(db_session)
    classification = _classify_follow_up(db_session, user_id)
    ProfileService(db_session).save(
        user_id,
        ProfileData(full_name="Alex Example", answers={"salary_expectations": "$150k"}),
    )
    service = ReplyDraftService(db_session)
    with patch.object(service, "_resolve_provider", return_value="heuristic"):
        result = service.draft(
            user_id,
            ReplyDraftRequest(classification_id=classification.id),
        )
    assert result.provider == "heuristic"
    assert result.status == "draft"
    assert "salary" in result.body_text.lower() or "$150" in result.body_text
    assert result.classification_id == classification.id

    listed = service.list_for_user(user_id)
    assert len(listed) == 1
    assert listed[0].id == result.id


def test_draft_is_idempotent_without_regenerate(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id, _job = _seed_applied_job(db_session)
    classification = _classify_follow_up(db_session, user_id)
    ProfileService(db_session).save(user_id, ProfileData(full_name="Alex Example"))
    service = ReplyDraftService(db_session)
    with patch.object(service, "_resolve_provider", return_value="heuristic"):
        first = service.draft(user_id, ReplyDraftRequest(classification_id=classification.id))
        second = service.draft(user_id, ReplyDraftRequest(classification_id=classification.id))
    assert first.id == second.id


def test_draft_rejects_non_draftable_labels(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id, _job = _seed_applied_job(db_session)
    ProfileService(db_session).save(user_id, ProfileData(full_name="Alex Example"))
    row = InboxClassification(
        user_id=user_id,
        message_uid=1,
        label="rejection",
        confidence=0.9,
        reason="test",
        provider="heuristic",
        subject="No",
        from_addr="hr@acme.com",
    )
    db_session.add(row)
    db_session.flush()
    service = ReplyDraftService(db_session)
    try:
        service.draft(user_id, ReplyDraftRequest(classification_id=row.id))
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert "follow-up" in str(exc).lower()
