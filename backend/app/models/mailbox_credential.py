"""MailboxCredential: encrypted IMAP/SMTP settings for inbox automation.

One row per user. The secret payload is a JSON `MailboxConfig` encrypted with
Fernet before storage. Dev-only — used when `INBOX_AGENT_ENABLED=true`.
"""

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class MailboxCredential(Base, TimestampMixin):
    __tablename__ = "mailbox_credential"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    connector_type: Mapped[str] = mapped_column(String(32), nullable=False, default="imap_smtp")
    secret_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    routing_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    user: Mapped["User"] = relationship(back_populates="mailbox_credential")
