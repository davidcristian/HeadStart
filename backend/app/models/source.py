"""Source: a job site plus the scraper adapter that handles it."""

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.search import Search
    from app.models.site_credential import SiteCredential
    from app.models.user import User


class Source(Base, TimestampMixin):
    __tablename__ = "source"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    adapter_key: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    base_url: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    default_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped["User"] = relationship(back_populates="sources")
    searches: Mapped[list["Search"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    credentials: Mapped[list["SiteCredential"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
