"""DataRequestLog: audit trail for GDPR export and account-deletion requests."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.user import User


class DataRequestLog(Base):
    __tablename__ = "data_request_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), index=True, nullable=True
    )
    user_email: Mapped[str] = mapped_column(String(320), nullable=False)
    request_type: Mapped[str] = mapped_column(String(20), nullable=False)  # export | delete
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

    user: Mapped["User | None"] = relationship()
