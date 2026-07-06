"""Search endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_verified_user
from app.models.user import User
from app.schemas.search import SearchCreate, SearchRead, SearchUpdate
from app.schemas.search_run import SearchRunRead
from app.services.search_runs import SearchRunService
from app.services.searches import SearchService
from app.worker.tasks import run_search_run_task

router = APIRouter()


@router.get("", response_model=list[SearchRead])
def list_searches(
    db: Session = Depends(get_db), user: User = Depends(get_verified_user)
) -> list[SearchRead]:
    return SearchService(db).list_reads(user.id)


@router.post("", response_model=SearchRead, status_code=status.HTTP_201_CREATED)
def create_search(
    data: SearchCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> SearchRead:
    return SearchService(db).create_read(user.id, data)


@router.get("/{search_id}", response_model=SearchRead)
def get_search(
    search_id: int, db: Session = Depends(get_db), user: User = Depends(get_verified_user)
) -> SearchRead:
    return SearchService(db).get_read(search_id, user.id)


@router.patch("/{search_id}", response_model=SearchRead)
def update_search(
    search_id: int,
    data: SearchUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> SearchRead:
    return SearchService(db).update_read(search_id, user.id, data)


@router.delete("/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_search(
    search_id: int, db: Session = Depends(get_db), user: User = Depends(get_verified_user)
) -> None:
    SearchService(db).delete(search_id, user.id)


@router.post(
    "/{search_id}/run",
    response_model=SearchRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def run_search_now(
    search_id: int, db: Session = Depends(get_db), user: User = Depends(get_verified_user)
) -> SearchRunRead:
    """Queue the search pipeline; poll GET /search-runs/{id} for counts."""
    queued = SearchRunService(db).enqueue(user.id, search_id)
    db.commit()
    run_search_run_task.delay(queued.id, user.id, search_id)
    return queued
