"""NotificationTarget: a delivery destination (e.g. an ntfy topic)."""

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.search import Search
    from app.models.user import User


class NotificationTarget(Base, TimestampMixin):
    __tablename__ = "notification_target"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Matches a registered notifier key (e.g. "ntfy").
    type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    user: Mapped["User"] = relationship(back_populates="targets")
    searches: Mapped[list["Search"]] = relationship(back_populates="target")
