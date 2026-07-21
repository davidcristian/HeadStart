"""Celery tasks for async resume / cover-letter generation."""

from __future__ import annotations

from app.core.db import session_scope
from app.core.logging import get_logger
from app.worker.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="app.worker.tasks.generate_resume", bind=True, max_retries=0)
def generate_resume_task(
    self: object,
    generation_id: int,
    user_id: int,
    job_id: int,
) -> dict[str, object]:
    """Run one queued tailored-resume generation in the worker."""
    return _run_document_generation(generation_id, user_id, job_id, kind="resume")


@celery_app.task(name="app.worker.tasks.generate_cover_letter", bind=True, max_retries=0)
def generate_cover_letter_task(
    self: object,
    generation_id: int,
    user_id: int,
    job_id: int,
) -> dict[str, object]:
    """Run one queued cover-letter generation in the worker."""
    return _run_document_generation(generation_id, user_id, job_id, kind="cover_letter")


def _run_document_generation(
    generation_id: int,
    user_id: int,
    job_id: int,
    *,
    kind: str,
) -> dict[str, object]:
    from app.services.document_generations import DocumentGenerationService

    with session_scope() as session:
        claimed = DocumentGenerationService(session).claim(generation_id)
    if claimed is None:
        logger.info(
            "document_generation skipped (not queued) id=%s kind=%s user=%s job=%s",
            generation_id,
            kind,
            user_id,
            job_id,
        )
        return {"generation_id": generation_id, "status": "skipped", "error": "not_queued"}

    with session_scope() as session:
        service = DocumentGenerationService(session)
        if kind == "resume":
            service.complete_resume(generation_id, user_id, job_id)
        else:
            service.complete_cover_letter(generation_id, user_id, job_id)
        row = service.repo.get(generation_id)
        status = row.status if row is not None else "missing"
        error = row.error if row is not None else None

    logger.info(
        "document_generation id=%s kind=%s user=%s job=%s status=%s",
        generation_id,
        kind,
        user_id,
        job_id,
        status,
    )
    return {"generation_id": generation_id, "status": status, "error": error}
