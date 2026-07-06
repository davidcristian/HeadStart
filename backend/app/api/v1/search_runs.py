"""Search run poll endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_verified_user
from app.models.user import User
from app.schemas.search_run import SearchRunRead
from app.services.search_runs import SearchRunService

router = APIRouter()


@router.get("/{run_id}", response_model=SearchRunRead)
def get_search_run(
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> SearchRunRead:
    """Return one manual search-run job for polling."""
    return SearchRunService(db).get_for_user(user.id, run_id)
