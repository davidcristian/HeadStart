"""ApplicationProfile: one encrypted candidate profile per user.

Holds the structured data an auto-apply flow needs (contact details, resume
text, a cover-letter template, and free-form per-field answers). The payload is
PII, so the whole JSON blob is Fernet-encrypted before storage; only
`data_ciphertext` ever reaches the database. Unlike `site_credential` secrets,
the decrypted profile *is* returned to its owner — they must read and edit it.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, utcnow

if TYPE_CHECKING:
    from app.models.user import User


class ApplicationProfile(Base, TimestampMixin):
    __tablename__ = "application_profile"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    # Fernet-encrypted JSON of the candidate profile. Never plaintext.
    data_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="application_profile")
