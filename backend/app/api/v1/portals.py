"""Curated employer portal catalog."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.portals.catalog import PortalCategory
from app.schemas.portal import PortalListRead
from app.services.portals import PortalCatalogService

router = APIRouter()


@router.get("", response_model=PortalListRead)
def list_portals(
    category: PortalCategory | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PortalListRead:
    """List curated FAANG-adjacent, unicorn, and AI employer portals."""
    return PortalCatalogService(db).list_for_user(user, category=category, query=q)
