"""Admin endpoints (user management and global stats)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_db
from app.models.user import User
from app.schemas.admin import AdminStatsRead, AdminUserRead, AdminUserUpdate
from app.services.admin import AdminService

router = APIRouter()


@router.get("/users", response_model=list[AdminUserRead])
def list_users(
    db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)
) -> list[AdminUserRead]:
    return AdminService(db).list_users()


@router.patch("/users/{user_id}", response_model=AdminUserRead)
def update_user(
    user_id: int,
    data: AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> AdminUserRead:
    return AdminService(db).update_user(user_id, admin.id, data)


@router.get("/stats", response_model=AdminStatsRead)
def get_stats(
    db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)
) -> AdminStatsRead:
    return AdminService(db).get_stats()
