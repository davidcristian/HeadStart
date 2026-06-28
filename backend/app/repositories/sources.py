"""Data access for Source. Queries only — no business logic."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.source import Source


class SourceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(self, user_id: int) -> list[Source]:
        return list(
            self.session.scalars(
                select(Source).where(Source.user_id == user_id).order_by(Source.id)
            )
        )

    def get(self, source_id: int, user_id: int) -> Source | None:
        return self.session.scalar(
            select(Source).where(Source.id == source_id, Source.user_id == user_id)
        )

    def add(self, source: Source) -> Source:
        self.session.add(source)
        self.session.flush()
        return source

    def delete(self, source: Source) -> None:
        self.session.delete(source)
