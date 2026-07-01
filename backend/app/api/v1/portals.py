"""Curated employer portal catalog."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.portals.catalog import PortalCategory
from app.schemas.portal import (
    PortalListRead,
    PortalSearchRequest,
    PortalSearchResultRead,
    PortalSubscribeRequest,
    PortalSubscribeResultRead,
)
from app.services.portal_search import PortalSearchService
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


@router.post("/search", response_model=PortalSearchResultRead)
def search_portals(
    data: PortalSearchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PortalSearchResultRead:
    """Search job listings across curated portals (Pro+)."""
    return PortalSearchService(db).search(user, data)


@router.post("/subscribe", response_model=PortalSubscribeResultRead)
def subscribe_portals(
    data: PortalSubscribeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PortalSubscribeResultRead:
    """Create sources and searches for curated portals in one step (Pro+)."""
    return PortalSearchService(db).subscribe(user, data)
