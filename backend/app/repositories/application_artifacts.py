"""Data access for ApplicationArtifact."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application_artifact import ApplicationArtifact


class ApplicationArtifactRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, artifact: ApplicationArtifact) -> ApplicationArtifact:
        self.session.add(artifact)
        self.session.flush()
        return artifact

    def get_for_user(self, artifact_id: int, user_id: int) -> ApplicationArtifact | None:
        """Return one artifact when it belongs to the user."""
        stmt = select(ApplicationArtifact).where(
            ApplicationArtifact.id == artifact_id,
            ApplicationArtifact.user_id == user_id,
        )
        return self.session.scalar(stmt)

    def get_by_hash(self, user_id: int, content_sha256: str) -> ApplicationArtifact | None:
        """Return an existing artifact for the same user and content hash."""
        stmt = select(ApplicationArtifact).where(
            ApplicationArtifact.user_id == user_id,
            ApplicationArtifact.content_sha256 == content_sha256,
        )
        return self.session.scalar(stmt)
