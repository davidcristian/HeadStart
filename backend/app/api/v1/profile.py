"""Application-profile endpoints. Singleton per user; encrypted at rest."""

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_verified_user
from app.core.config import settings
from app.core.exceptions import ValidationError
from app.models.user import User
from app.schemas.profile import ProfileData, ProfileRead
from app.services.profiles import ProfileService

router = APIRouter()

_READ_CHUNK_BYTES = 64 * 1024


async def _read_bounded_upload(file: UploadFile, max_bytes: int) -> bytes:
    """Stream an upload into memory without reading more than max_bytes."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ValidationError(f"Resume file exceeds the {max_bytes // 1_048_576} MB limit")
        chunks.append(chunk)
    if total == 0:
        raise ValidationError("Resume file is empty")
    return b"".join(chunks)


@router.get("", response_model=ProfileRead)
def get_profile(
    db: Session = Depends(get_db), user: User = Depends(get_verified_user)
) -> ProfileRead:
    return ProfileService(db).get(user.id)


@router.put("", response_model=ProfileRead)
def save_profile(
    data: ProfileData,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> ProfileRead:
    return ProfileService(db).save(user.id, data)


@router.put("/resume", response_model=ProfileRead)
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> ProfileRead:
    """Upload or replace the user's resume file (PDF or Word)."""
    content = await _read_bounded_upload(file, settings.profile_resume_max_bytes)
    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "resume.pdf"
    return ProfileService(db).save_resume(
        user.id,
        filename=filename,
        content_type=content_type,
        data=content,
    )


@router.delete(
    "/resume",
    response_model=ProfileRead,
    status_code=status.HTTP_200_OK,
)
def delete_resume(
    db: Session = Depends(get_db), user: User = Depends(get_verified_user)
) -> ProfileRead:
    """Clear the resume file and return the updated profile (state-returning DELETE).

    Unlike resource DELETEs that return 204, this keeps other profile fields and
    returns ProfileRead so clients can refresh UI state without a follow-up GET.
    """
    return ProfileService(db).delete_resume(user.id)


@router.put("/resume-template", response_model=ProfileRead)
async def upload_resume_template(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> ProfileRead:
    """Upload or replace the user's LaTeX resume template (.tex or .zip bundle)."""
    filename = file.filename or "resume.tex"
    max_bytes = (
        settings.profile_resume_template_bundle_max_bytes
        if filename.lower().endswith(".zip")
        else settings.profile_resume_template_max_bytes
    )
    content = await _read_bounded_upload(file, max_bytes)
    content_type = file.content_type or "application/octet-stream"
    return ProfileService(db).save_resume_template(
        user.id,
        filename=filename,
        content_type=content_type,
        data=content,
    )


@router.delete(
    "/resume-template",
    response_model=ProfileRead,
    status_code=status.HTTP_200_OK,
)
def delete_resume_template(
    db: Session = Depends(get_db), user: User = Depends(get_verified_user)
) -> ProfileRead:
    """Clear the LaTeX template and return the updated profile (state-returning DELETE).

    Same contract as DELETE /profile/resume: HTTP 200 + ProfileRead, not 204.
    """
    return ProfileService(db).delete_resume_template(user.id)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(db: Session = Depends(get_db), user: User = Depends(get_verified_user)) -> None:
    ProfileService(db).delete(user.id)
