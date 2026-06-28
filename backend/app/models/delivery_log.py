"""DeliveryLog: audit trail of notification attempts."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.notification_target import NotificationTarget
    from app.models.seen_job import SeenJob


class DeliveryLog(Base):
    __tablename__ = "delivery_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    seen_job_id: Mapped[int] = mapped_column(
        ForeignKey("seen_job.id", ondelete="CASCADE"), index=True, nullable=False
    )
    target_id: Mapped[int | None] = mapped_column(
        ForeignKey("notification_target.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[str] = mapped_column(String(20), nullable=False)  # sent | failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    seen_job: Mapped["SeenJob"] = relationship(back_populates="deliveries")
    target: Mapped["NotificationTarget | None"] = relationship()
