"""Singleton row used to serialize account registration."""

from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RegistrationLock(Base):
    __tablename__ = "registration_lock"

    id: Mapped[int] = mapped_column(primary_key=True)
    bootstrap_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Permanent latch: once True, never cleared by user deletion.
    bootstrap_claimed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
