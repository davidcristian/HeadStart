"""ApplicationLog: audit trail of auto-apply attempts."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.seen_job import SeenJob


class ApplicationLog(Base):
    __tablename__ = "application_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    seen_job_id: Mapped[int] = mapped_column(
        ForeignKey("seen_job.id", ondelete="CASCADE"), index=True, nullable=False
    )

    status: Mapped[str] = mapped_column(String(20), nullable=False)  # submitted | dry_run | failed
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    external_application_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    seen_job: Mapped["SeenJob"] = relationship(back_populates="application_logs")
