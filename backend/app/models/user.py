"""User: an account that owns its own sources, searches, targets, and creds."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.notification_target import NotificationTarget
    from app.models.password_reset_token import PasswordResetToken
    from app.models.search import Search
    from app.models.site_credential import SiteCredential
    from app.models.source import Source


class User(Base, TimestampMixin):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # The first registered user becomes admin (see AuthService.register).
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    sources: Mapped[list["Source"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    searches: Mapped[list["Search"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    targets: Mapped[list["NotificationTarget"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    credentials: Mapped[list["SiteCredential"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
