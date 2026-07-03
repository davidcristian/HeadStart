"""InboxPollState: last processed mailbox UID per user for beat orchestration."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class InboxPollState(Base, TimestampMixin):
    __tablename__ = "inbox_poll_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    last_polled_uid: Mapped[int | None] = mapped_column(nullable=True)

    user: Mapped["User"] = relationship(back_populates="inbox_poll_state")
