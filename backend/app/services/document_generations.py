"""Queue and complete async resume / cover-letter generation jobs."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.base import utcnow
from app.models.document_generation import DocumentGeneration
from app.repositories.document_generations import DocumentGenerationRepository
from app.schemas.document_generation import DocumentGenerationRead
from app.services.cover_letters import CoverLetterService
from app.services.jobs import JobService
from app.services.profiles import ProfileService
from app.services.resumes import ResumeService

logger = get_logger(__name__)

KIND_RESUME = "resume"
KIND_COVER_LETTER = "cover_letter"


class DocumentGenerationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = DocumentGenerationRepository(session)

    def enqueue_resume(self, user_id: int, job_id: int) -> DocumentGenerationRead:
        """Validate and queue a tailored resume generation for the worker."""
        self._assert_can_generate_resume(user_id, job_id)
        return self._enqueue(user_id, job_id, KIND_RESUME)

    def enqueue_cover_letter(self, user_id: int, job_id: int) -> DocumentGenerationRead:
        """Validate and queue a cover-letter generation for the worker."""
        self._assert_can_generate_cover_letter(user_id, job_id)
        return self._enqueue(user_id, job_id, KIND_COVER_LETTER)

    def get_for_user(self, user_id: int, generation_id: int) -> DocumentGenerationRead:
        """Return one generation job scoped to the authenticated user."""
        row = self.repo.get_for_user(generation_id, user_id)
        if row is None:
            raise NotFoundError(f"Document generation {generation_id} not found")
        return DocumentGenerationRead.model_validate(row)

    def claim(self, generation_id: int) -> DocumentGeneration | None:
        """Lease a queued job (queued → processing) before LLM/LaTeX work."""
        row = self.repo.get(generation_id)
        if row is None or row.status != "queued":
            return None
        row.status = "processing"
        row.updated_at = utcnow()
        self.session.flush()
        return row

    def complete_resume(self, generation_id: int, user_id: int, job_id: int) -> None:
        """Run resume generation and store the ready payload (or mark failed)."""
        self._run(generation_id, user_id, job_id, KIND_RESUME)

    def complete_cover_letter(self, generation_id: int, user_id: int, job_id: int) -> None:
        """Run cover-letter generation and store the ready payload (or mark failed)."""
        self._run(generation_id, user_id, job_id, KIND_COVER_LETTER)

    def _enqueue(self, user_id: int, job_id: int, kind: str) -> DocumentGenerationRead:
        now = utcnow()
        row = DocumentGeneration(
            user_id=user_id,
            seen_job_id=job_id,
            kind=kind,
            status="queued",
            created_at=now,
            updated_at=now,
        )
        self.repo.add(row)
        return DocumentGenerationRead.model_validate(row)

    def _run(self, generation_id: int, user_id: int, job_id: int, kind: str) -> None:
        row = self.repo.get(generation_id)
        if row is None:
            raise NotFoundError(f"Document generation {generation_id} not found")
        if row.user_id != user_id or row.seen_job_id != job_id or row.kind != kind:
            raise NotFoundError(f"Document generation {generation_id} not found")
        if row.status != "processing":
            return
        try:
            if kind == KIND_RESUME:
                result: dict[str, Any] = ResumeService(self.session).generate(user_id, job_id)
            else:
                result = CoverLetterService(self.session).generate(user_id, job_id)
        except Exception as exc:
            logger.warning(
                "document_generation failed id=%s kind=%s user=%s job=%s: %s",
                generation_id,
                kind,
                user_id,
                job_id,
                exc,
            )
            row.status = "failed"
            row.error = str(exc)
            row.result = None
            row.updated_at = utcnow()
            self.session.flush()
            return
        row.status = "ready"
        row.error = None
        row.result = result
        row.updated_at = utcnow()
        self.session.flush()

    def _assert_can_generate_resume(self, user_id: int, job_id: int) -> None:
        from app.core.config import settings

        if not bool(getattr(settings, "resume_curation_enabled", True)):
            raise ValidationError("Resume curation is disabled")
        JobService(self.session).get(job_id, user_id)
        profile = ProfileService(self.session).get_for_apply(user_id)
        if not profile.exists:
            raise ValidationError("Save an application profile before generating a resume")

    def _assert_can_generate_cover_letter(self, user_id: int, job_id: int) -> None:
        from app.core.config import settings

        if not bool(getattr(settings, "cover_letters_enabled", True)):
            raise ValidationError("Cover letter generation is disabled")
        JobService(self.session).get(job_id, user_id)
        profile = ProfileService(self.session).get_for_apply(user_id)
        if not profile.exists:
            raise ValidationError("Save an application profile before generating a cover letter")
