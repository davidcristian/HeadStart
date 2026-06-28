"""Search endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.meta import MessageRead
from app.schemas.search import SearchCreate, SearchRead, SearchUpdate
from app.services.searches import SearchService

router = APIRouter()


@router.get("", response_model=list[SearchRead])
def list_searches(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[SearchRead]:
    return [SearchRead.model_validate(s) for s in SearchService(db).list_all(user.id)]


@router.post("", response_model=SearchRead, status_code=status.HTTP_201_CREATED)
def create_search(
    data: SearchCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SearchRead:
    return SearchRead.model_validate(SearchService(db).create(user.id, data))


@router.get("/{search_id}", response_model=SearchRead)
def get_search(
    search_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> SearchRead:
    return SearchRead.model_validate(SearchService(db).get(search_id, user.id))


@router.patch("/{search_id}", response_model=SearchRead)
def update_search(
    search_id: int,
    data: SearchUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SearchRead:
    return SearchRead.model_validate(SearchService(db).update(search_id, user.id, data))


@router.delete("/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_search(
    search_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> None:
    SearchService(db).delete(search_id, user.id)


@router.post("/{search_id}/run", response_model=MessageRead, status_code=status.HTTP_202_ACCEPTED)
def run_search_now(
    search_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> MessageRead:
    """Make the search due now; the scheduler picks it up on the next tick."""
    SearchService(db).mark_due(search_id, user.id)
    return MessageRead(detail="Search marked due; it will run on the next scheduler tick.")
