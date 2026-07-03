"""InboxReplyDraft: persisted recruiter reply drafts (dry-run; no auto-send yet)."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.inbox_classification import InboxClassification
    from app.models.seen_job import SeenJob
    from app.models.user import User


class InboxReplyDraft(Base):
    __tablename__ = "inbox_reply_draft"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "inbox_classification_id",
            name="uq_inbox_reply_draft_user_classification",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    inbox_classification_id: Mapped[int] = mapped_column(
        ForeignKey("inbox_classification.id", ondelete="CASCADE"), index=True, nullable=False
    )
    seen_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("seen_job.id", ondelete="SET NULL"), index=True, nullable=True
    )

    message_uid: Mapped[int] = mapped_column(nullable=False)
    subject: Mapped[str] = mapped_column(String(998), nullable=False, default="")
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    fallback: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="inbox_reply_drafts")
    classification: Mapped["InboxClassification"] = relationship()
    seen_job: Mapped["SeenJob | None"] = relationship()
