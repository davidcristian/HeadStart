"""Notification target endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_verified_user
from app.models.user import User
from app.notifiers.types import DeliveryResult
from app.schemas.target import TargetCreate, TargetRead, TargetUpdate
from app.services.targets import TargetService

router = APIRouter()


@router.get("", response_model=list[TargetRead])
def list_targets(
    db: Session = Depends(get_db), user: User = Depends(get_verified_user)
) -> list[TargetRead]:
    return [TargetRead.model_validate(t) for t in TargetService(db).list_all(user.id)]


@router.post("", response_model=TargetRead, status_code=status.HTTP_201_CREATED)
def create_target(
    data: TargetCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> TargetRead:
    return TargetRead.model_validate(TargetService(db).create(user.id, data))


@router.get("/{target_id}", response_model=TargetRead)
def get_target(
    target_id: int, db: Session = Depends(get_db), user: User = Depends(get_verified_user)
) -> TargetRead:
    return TargetRead.model_validate(TargetService(db).get(target_id, user.id))


@router.patch("/{target_id}", response_model=TargetRead)
def update_target(
    target_id: int,
    data: TargetUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> TargetRead:
    return TargetRead.model_validate(TargetService(db).update(target_id, user.id, data))


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_target(
    target_id: int, db: Session = Depends(get_db), user: User = Depends(get_verified_user)
) -> None:
    TargetService(db).delete(target_id, user.id)


@router.post("/{target_id}/test", response_model=DeliveryResult)
def test_target(
    target_id: int, db: Session = Depends(get_db), user: User = Depends(get_verified_user)
) -> DeliveryResult:
    """Send a sample notification to verify the target is configured correctly."""
    return TargetService(db).send_test(target_id, user.id)
