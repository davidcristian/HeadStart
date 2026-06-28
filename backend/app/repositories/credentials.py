"""Data access for SiteCredential. Queries only — no business logic."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.site_credential import SiteCredential


class CredentialRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(self, user_id: int) -> list[SiteCredential]:
        return list(
            self.session.scalars(
                select(SiteCredential)
                .where(SiteCredential.user_id == user_id)
                .order_by(SiteCredential.id)
            )
        )

    def get(self, credential_id: int, user_id: int) -> SiteCredential | None:
        return self.session.scalar(
            select(SiteCredential).where(
                SiteCredential.id == credential_id,
                SiteCredential.user_id == user_id,
            )
        )

    def for_source(self, user_id: int, source_id: int) -> SiteCredential | None:
        """The enabled credential a worker should inject for this user+source."""
        return self.session.scalar(
            select(SiteCredential)
            .where(
                SiteCredential.user_id == user_id,
                SiteCredential.source_id == source_id,
                SiteCredential.enabled.is_(True),
            )
            .order_by(SiteCredential.id.desc())
        )

    def add(self, credential: SiteCredential) -> SiteCredential:
        self.session.add(credential)
        self.session.flush()
        return credential

    def delete(self, credential: SiteCredential) -> None:
        self.session.delete(credential)
