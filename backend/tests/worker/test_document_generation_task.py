"""Worker + service coverage for document generation (API-01)."""

from contextlib import contextmanager
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.models.base import utcnow
from app.models.document_generation import DocumentGeneration
from app.models.seen_job import SeenJob
from app.schemas.profile import ProfileData
from app.services.document_generations import DocumentGenerationService
from app.services.profiles import ProfileService
from app.services.resumes import ResumeService
from app.worker.tasks import generate_cover_letter_task, generate_resume_task
from tests.worker.test_pipeline import _make_search


def _seed_job(session: Session, *, with_profile: bool = True) -> tuple[int, int]:
    search = _make_search(session)
    job = SeenJob(
        search_id=search.id,
        external_id="docgen-1",
        hash="docgen-hash-1",
        title="Senior Engineer",
        company="ACME",
        location="Remote",
        url="https://boards.greenhouse.io/acme/jobs/docgen-1",
        status="new",
    )
    session.add(job)
    session.flush()
    if with_profile:
        ProfileService(session).save(
            search.user_id,
            ProfileData(
                full_name="Ada Lovelace",
                email="ada@example.com",
                skills=["Python"],
                cover_letter_template="Dear {company} team, I am excited about {job_title}.",
            ),
        )
    session.commit()
    return search.user_id, job.id


def _scope(session: Session):
    @contextmanager
    def test_scope():
        yield session
        session.commit()

    return test_scope


def test_claim_skips_non_queued(db_session: Session) -> None:
    user_id, job_id = _seed_job(db_session, with_profile=False)
    row = DocumentGeneration(
        user_id=user_id,
        seen_job_id=job_id,
        kind="resume",
        status="ready",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db_session.add(row)
    db_session.commit()
    assert DocumentGenerationService(db_session).claim(row.id) is None


def test_generate_resume_task_skips_when_not_queued(db_session: Session) -> None:
    user_id, job_id = _seed_job(db_session, with_profile=False)
    row = DocumentGeneration(
        user_id=user_id,
        seen_job_id=job_id,
        kind="resume",
        status="processing",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db_session.add(row)
    db_session.commit()
    with patch("app.worker.tasks.session_scope", _scope(db_session)):
        result = generate_resume_task(row.id, user_id, job_id)
    assert result["status"] == "skipped"


def test_complete_marks_failed_on_generator_error(db_session: Session) -> None:
    user_id, job_id = _seed_job(db_session, with_profile=False)
    service = DocumentGenerationService(db_session)
    row = DocumentGeneration(
        user_id=user_id,
        seen_job_id=job_id,
        kind="resume",
        status="processing",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db_session.add(row)
    db_session.flush()
    service.complete_resume(row.id, user_id, job_id)
    db_session.refresh(row)
    assert row.status == "failed"
    assert row.error


def test_complete_noop_when_not_processing(db_session: Session) -> None:
    user_id, job_id = _seed_job(db_session, with_profile=False)
    row = DocumentGeneration(
        user_id=user_id,
        seen_job_id=job_id,
        kind="cover_letter",
        status="queued",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db_session.add(row)
    db_session.flush()
    DocumentGenerationService(db_session).complete_cover_letter(row.id, user_id, job_id)
    db_session.refresh(row)
    assert row.status == "queued"


def test_complete_raises_when_missing(db_session: Session) -> None:
    with pytest.raises(NotFoundError):
        DocumentGenerationService(db_session).complete_resume(999999, 1, 1)


def test_complete_raises_on_mismatched_owner(db_session: Session) -> None:
    user_id, job_id = _seed_job(db_session, with_profile=False)
    row = DocumentGeneration(
        user_id=user_id,
        seen_job_id=job_id,
        kind="resume",
        status="processing",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db_session.add(row)
    db_session.flush()
    with pytest.raises(NotFoundError):
        DocumentGenerationService(db_session).complete_resume(row.id, user_id + 1, job_id)


def test_enqueue_resume_disabled(db_session: Session) -> None:
    user_id, job_id = _seed_job(db_session)
    with (
        patch.object(settings, "resume_curation_enabled", False),
        pytest.raises(ValidationError, match="disabled"),
    ):
        DocumentGenerationService(db_session).enqueue_resume(user_id, job_id)


def test_enqueue_cover_letter_disabled(db_session: Session) -> None:
    user_id, job_id = _seed_job(db_session)
    with (
        patch.object(settings, "cover_letters_enabled", False),
        pytest.raises(ValidationError, match="disabled"),
    ):
        DocumentGenerationService(db_session).enqueue_cover_letter(user_id, job_id)


def test_generate_cover_letter_task_skips_when_not_queued(db_session: Session) -> None:
    user_id, job_id = _seed_job(db_session, with_profile=False)
    with patch("app.worker.tasks.session_scope", _scope(db_session)):
        result = generate_cover_letter_task(999999, user_id, job_id)
    assert result["status"] == "skipped"


def test_worker_resume_success_path(db_session: Session) -> None:
    user_id, job_id = _seed_job(db_session)
    row = DocumentGeneration(
        user_id=user_id,
        seen_job_id=job_id,
        kind="resume",
        status="queued",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db_session.add(row)
    db_session.commit()

    with (
        patch("app.worker.tasks.session_scope", _scope(db_session)),
        patch.object(ResumeService, "_compile_pdf", return_value=b"%PDF-1.4\nok\n"),
    ):
        result = generate_resume_task(row.id, user_id, job_id)
    assert result["status"] == "ready"


def test_worker_cover_letter_success_path(db_session: Session) -> None:
    user_id, job_id = _seed_job(db_session)
    row = DocumentGeneration(
        user_id=user_id,
        seen_job_id=job_id,
        kind="cover_letter",
        status="queued",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db_session.add(row)
    db_session.commit()

    with patch("app.worker.tasks.session_scope", _scope(db_session)):
        result = generate_cover_letter_task(row.id, user_id, job_id)
    assert result["status"] == "ready"
