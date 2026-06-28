"""SiteCredential: encrypted cookies/headers/session for a user + source.

The actual secret payload (a JSON object of `{cookies, headers, session}`) is
encrypted with Fernet *before* it is stored here; only ciphertext lives in the
database. Decryption happens at the edge (the pipeline) right before a scrape.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.source import Source
    from app.models.user import User


class SiteCredential(Base, TimestampMixin):
    __tablename__ = "site_credential"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("source.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    # Fernet-encrypted JSON of {cookies, headers, session}. Never plaintext.
    secret_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped["User"] = relationship(back_populates="credentials")
    source: Mapped["Source"] = relationship(back_populates="credentials")
