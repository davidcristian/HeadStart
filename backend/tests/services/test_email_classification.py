"""Service tests for email classification."""

from datetime import UTC, datetime
from unittest.mock import patch

from sqlalchemy.orm import Session

from app.core.config import settings
from app.email_classifiers import EmailClassificationResult, EmailClassifyContext
from app.inbox.types import InboxMessage
from app.models.application_log import ApplicationLog
from app.models.seen_job import SeenJob
from app.schemas.inbox_classification import EmailClassifyRequest
from app.services.email_classification import EmailClassificationService
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


class StubClassifier:
    def __init__(self, label: str) -> None:
        self.label = label

    def classify(self, ctx: EmailClassifyContext) -> EmailClassificationResult:
        return EmailClassificationResult(
            label=self.label,
            confidence=0.9,
            reason="stub",
        )


def test_classify_persists_heuristic_result(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id, _job = _seed_applied_job(db_session)
    service = EmailClassificationService(db_session)
    user = service.users.get(user_id)
    assert user is not None
    with patch.object(service, "_resolve_provider", return_value="heuristic"):
        result = service.classify(
            user_id,
            EmailClassifyRequest(
                message=InboxMessage(
                    uid=42,
                    from_addr="hr@careers.acme.com",
                    subject="Unfortunately",
                    body_text="We will not be moving forward.",
                )
            ),
        )
    assert result.label == "rejection"
    assert result.provider == "heuristic"
    assert result.message_uid == 42

    listed = service.list_for_user(user_id)
    assert len(listed) == 1
    assert listed[0].id == result.id


def test_classify_is_idempotent_per_message_uid(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id, _job = _seed_applied_job(db_session)
    service = EmailClassificationService(db_session)
    request = EmailClassifyRequest(
        message=InboxMessage(uid=7, subject="Hello", body_text="General update.")
    )
    with patch.object(service, "_resolve_provider", return_value="heuristic"):
        first = service.classify(user_id, request)
        second = service.classify(user_id, request)
    assert first.id == second.id


def test_classify_falls_back_when_llm_fails(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id, _job = _seed_applied_job(db_session)
    service = EmailClassificationService(db_session)

    def factory(key: str, runtime: object) -> object:
        if key == "heuristic":
            return StubClassifier("general")
        raise RuntimeError("network down")

    service._factory = factory  # type: ignore[method-assign]
    with patch.object(service, "_resolve_provider", return_value="openai"):
        result = service.classify(
            user_id,
            EmailClassifyRequest(
                message=InboxMessage(uid=9, subject="Update", body_text="Thanks for applying.")
            ),
        )
    assert result.provider == "heuristic"
    assert result.fallback is True
