"""Per-user AI summary provider preferences."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_verified_user
from app.models.user import User
from app.schemas.summary_preferences import SummaryPreferencesRead, SummaryPreferencesUpdate
from app.services.summary_preferences import SummaryPreferencesService

router = APIRouter()


@router.get("", response_model=SummaryPreferencesRead)
def get_summary_preferences(
    db: Session = Depends(get_db), user: User = Depends(get_verified_user)
) -> SummaryPreferencesRead:
    return SummaryPreferencesService(db).get(user)


@router.patch("", response_model=SummaryPreferencesRead)
def update_summary_preferences(
    data: SummaryPreferencesUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> SummaryPreferencesRead:
    return SummaryPreferencesService(db).update(user.id, data)
