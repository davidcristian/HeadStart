"""SeenJob: dedup ledger; one row per unique job ever seen for a search."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.delivery_log import DeliveryLog
    from app.models.search import Search


class SeenJob(Base):
    __tablename__ = "seen_job"
    __table_args__ = (
        UniqueConstraint("search_id", "external_id", name="uq_seen_job_search_external"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    search_id: Mapped[int] = mapped_column(
        ForeignKey("search.id", ondelete="CASCADE"), index=True, nullable=False
    )

    external_id: Mapped[str] = mapped_column(String(500), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    company: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    location: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    salary: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    url: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    summary: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="new")
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    search: Mapped["Search"] = relationship(back_populates="seen_jobs")
    deliveries: Mapped[list["DeliveryLog"]] = relationship(
        back_populates="seen_job", cascade="all, delete-orphan"
    )
