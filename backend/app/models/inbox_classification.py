"""InboxClassification: persisted email classification results."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.seen_job import SeenJob
    from app.models.user import User


class InboxClassification(Base):
    __tablename__ = "inbox_classification"
    __table_args__ = (UniqueConstraint("user_id", "message_uid", name="uq_inbox_class_user_uid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    seen_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("seen_job.id", ondelete="SET NULL"), index=True, nullable=True
    )

    message_uid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    label: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    fallback: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    subject: Mapped[str] = mapped_column(String(998), nullable=False, default="")
    from_addr: Mapped[str] = mapped_column(String(320), nullable=False, default="")
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    routed_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    routing_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    routing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="inbox_classifications")
    seen_job: Mapped["SeenJob | None"] = relationship()
