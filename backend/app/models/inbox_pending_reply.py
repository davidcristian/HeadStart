"""InboxPendingReply: delayed auto-send queue for recruiter reply drafts."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.inbox_reply_draft import InboxReplyDraft
    from app.models.user import User


class InboxPendingReply(Base):
    __tablename__ = "inbox_pending_reply"
    __table_args__ = (
        UniqueConstraint(
            "inbox_reply_draft_id",
            name="uq_inbox_pending_reply_draft",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    inbox_reply_draft_id: Mapped[int] = mapped_column(
        ForeignKey("inbox_reply_draft.id", ondelete="CASCADE"), index=True, nullable=False
    )

    send_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="inbox_pending_replies")
    draft: Mapped["InboxReplyDraft"] = relationship(back_populates="pending_reply")
