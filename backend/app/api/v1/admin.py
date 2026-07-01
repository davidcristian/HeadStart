"""Admin endpoints (user management and global stats)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_db
from app.models.user import User
from app.schemas.admin import AdminStatsRead, AdminUserRead, AdminUserUpdate
from app.schemas.promo import (
    PromoCodeCreate,
    PromoCodeRead,
    PromoCodeUpdate,
    PromoRedemptionRead,
)
from app.services.admin import AdminService
from app.services.promo_codes import PromoCodeService

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


@router.get("/promo-codes", response_model=list[PromoCodeRead])
def list_promo_codes(
    db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)
) -> list[PromoCodeRead]:
    return PromoCodeService(db).list_codes()


@router.post("/promo-codes", response_model=PromoCodeRead, status_code=201)
def create_promo_code(
    data: PromoCodeCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> PromoCodeRead:
    return PromoCodeService(db).create_code(data)


@router.patch("/promo-codes/{promo_id}", response_model=PromoCodeRead)
def update_promo_code(
    promo_id: int,
    data: PromoCodeUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> PromoCodeRead:
    return PromoCodeService(db).update_code(promo_id, data)


@router.get("/promo-codes/{promo_id}/redemptions", response_model=list[PromoRedemptionRead])
def list_promo_redemptions(
    promo_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> list[PromoRedemptionRead]:
    return PromoCodeService(db).list_redemptions(promo_id)
