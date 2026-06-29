"""Application-profile endpoints. Singleton per user; encrypted at rest."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.profile import ProfileData, ProfileRead
from app.services.profiles import ProfileService

router = APIRouter()


@router.get("", response_model=ProfileRead)
def get_profile(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> ProfileRead:
    return ProfileService(db).get(user.id)


@router.put("", response_model=ProfileRead)
def save_profile(
    data: ProfileData,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProfileRead:
    return ProfileService(db).save(user.id, data)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    ProfileService(db).delete(user.id)
