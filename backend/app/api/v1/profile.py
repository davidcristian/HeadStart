"""Application-profile endpoints. Singleton per user; encrypted at rest."""

from fastapi import APIRouter, Depends, File, UploadFile, status
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


@router.put("/resume", response_model=ProfileRead)
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProfileRead:
    """Upload or replace the user's resume file (PDF or Word)."""
    content = await file.read()
    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "resume.pdf"
    return ProfileService(db).save_resume(
        user.id,
        filename=filename,
        content_type=content_type,
        data=content,
    )


@router.delete("/resume", response_model=ProfileRead)
def delete_resume(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> ProfileRead:
    """Remove the stored resume file without clearing other profile fields."""
    return ProfileService(db).delete_resume(user.id)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    ProfileService(db).delete(user.id)
