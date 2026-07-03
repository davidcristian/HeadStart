"""InboxReplySendLog: audit trail for autonomous recruiter reply decisions."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.inbox_reply_draft import InboxReplyDraft
    from app.models.user import User


class InboxReplySendLog(Base):
    __tablename__ = "inbox_reply_send_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    inbox_reply_draft_id: Mapped[int] = mapped_column(
        ForeignKey("inbox_reply_draft.id", ondelete="CASCADE"), index=True, nullable=False
    )
    inbox_pending_reply_id: Mapped[int | None] = mapped_column(
        ForeignKey("inbox_pending_reply.id", ondelete="SET NULL"), index=True, nullable=True
    )

    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    subject: Mapped[str] = mapped_column(String(998), nullable=False, default="")
    body_excerpt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

    user: Mapped["User"] = relationship(back_populates="inbox_reply_send_logs")
    draft: Mapped["InboxReplyDraft"] = relationship()
