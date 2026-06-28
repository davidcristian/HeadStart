"""PendingDigest: jobs queued for batched digest notification."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.search import Search
    from app.models.seen_job import SeenJob


class PendingDigest(Base):
    __tablename__ = "pending_digest"
    __table_args__ = (UniqueConstraint("seen_job_id", name="uq_pending_digest_seen_job"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    search_id: Mapped[int] = mapped_column(
        ForeignKey("search.id", ondelete="CASCADE"), index=True, nullable=False
    )
    seen_job_id: Mapped[int] = mapped_column(
        ForeignKey("seen_job.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    search: Mapped["Search"] = relationship(back_populates="pending_digests")
    seen_job: Mapped["SeenJob"] = relationship()
