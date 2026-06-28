"""Per-site credential endpoints. Secrets are write-only; reads expose metadata."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.credential import CredentialCreate, CredentialRead, CredentialUpdate
from app.services.credentials import CredentialService

router = APIRouter()


@router.get("", response_model=list[CredentialRead])
def list_credentials(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[CredentialRead]:
    return CredentialService(db).list_all(user.id)


@router.post("", response_model=CredentialRead, status_code=status.HTTP_201_CREATED)
def create_credential(
    data: CredentialCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CredentialRead:
    return CredentialService(db).create(user.id, data)


@router.get("/{credential_id}", response_model=CredentialRead)
def get_credential(
    credential_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> CredentialRead:
    return CredentialService(db).get_read(credential_id, user.id)


@router.patch("/{credential_id}", response_model=CredentialRead)
def update_credential(
    credential_id: int,
    data: CredentialUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CredentialRead:
    return CredentialService(db).update(credential_id, user.id, data)


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_credential(
    credential_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> None:
    CredentialService(db).delete(credential_id, user.id)
