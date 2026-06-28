"""Search: a saved query against a source, polled on an interval."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, utcnow

if TYPE_CHECKING:
    from app.models.notification_target import NotificationTarget
    from app.models.pending_digest import PendingDigest
    from app.models.seen_job import SeenJob
    from app.models.source import Source
    from app.models.user import User


class Search(Base, TimestampMixin):
    __tablename__ = "search"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("source.id", ondelete="CASCADE"), index=True, nullable=False
    )
    target_id: Mapped[int | None] = mapped_column(
        ForeignKey("notification_target.id", ondelete="SET NULL"), nullable=True
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    query_url: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    interval_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    notification_mode: Mapped[str] = mapped_column(String(20), default="immediate", nullable=False)
    digest_interval_seconds: Mapped[int] = mapped_column(Integer, default=3600, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_digest_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Defaults to "now" so a new search is due immediately. Drives catch-up.
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="searches")
    source: Mapped["Source"] = relationship(back_populates="searches")
    target: Mapped["NotificationTarget | None"] = relationship(back_populates="searches")
    seen_jobs: Mapped[list["SeenJob"]] = relationship(
        back_populates="search", cascade="all, delete-orphan"
    )
    pending_digests: Mapped[list["PendingDigest"]] = relationship(
        back_populates="search", cascade="all, delete-orphan"
    )
