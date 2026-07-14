"""ApplicationLog: audit trail of auto-apply attempts."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.application_artifact import ApplicationArtifact
    from app.models.seen_job import SeenJob

# Canonical persisted status values (DAT-09). Keep in sync with apply enqueue/claim
# and the in-flight partial unique index predicate below.
APPLICATION_LOG_STATUSES = frozenset({"queued", "processing", "submitted", "dry_run", "failed"})
APPLICATION_LOG_IN_FLIGHT_STATUSES = frozenset({"queued", "processing"})


class ApplicationLog(Base):
    __tablename__ = "application_log"
    __table_args__ = (
        Index(
            "uq_application_log_inflight_job",
            "seen_job_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'processing') AND dry_run IS FALSE"),
            sqlite_where=text("status IN ('queued', 'processing') AND dry_run = 0"),
        ),
        # Applications pipeline distinct subquery filters dry_run (DAT-03).
        Index("ix_application_log_dry_run_seen_job_id", "dry_run", "seen_job_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    seen_job_id: Mapped[int] = mapped_column(
        ForeignKey("seen_job.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # queued | processing | submitted | dry_run | failed — see APPLICATION_LOG_STATUSES
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    external_application_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tailored_resume_artifact_id: Mapped[int | None] = mapped_column(
        ForeignKey("application_artifact.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    seen_job: Mapped["SeenJob"] = relationship(back_populates="application_logs")
    tailored_resume_artifact: Mapped["ApplicationArtifact | None"] = relationship()
