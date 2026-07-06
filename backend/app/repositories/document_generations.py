"""Data access for DocumentGeneration."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_generation import DocumentGeneration


class DocumentGenerationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, row: DocumentGeneration) -> DocumentGeneration:
        """Persist a new generation job and flush so ``id`` is available."""
        self.session.add(row)
        self.session.flush()
        return row

    def get_for_user(self, generation_id: int, user_id: int) -> DocumentGeneration | None:
        """Return one generation job owned by ``user_id``."""
        stmt = select(DocumentGeneration).where(
            DocumentGeneration.id == generation_id,
            DocumentGeneration.user_id == user_id,
        )
        return self.session.scalar(stmt)

    def get(self, generation_id: int) -> DocumentGeneration | None:
        """Return one generation job by primary key."""
        return self.session.get(DocumentGeneration, generation_id)
