"""Admin request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.schemas.plan import PlanId


class AdminUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    is_admin: bool
    is_active: bool
    plan: PlanId
    created_at: datetime


class AdminUserUpdate(BaseModel):
    is_active: bool | None = None
    is_admin: bool | None = None
    plan: PlanId | None = None


class AdminSearchErrorRead(BaseModel):
    search_id: int
    search_name: str
    user_email: EmailStr
    last_error: str
    last_run_at: datetime | None


class AdminStatsRead(BaseModel):
    users_total: int
    users_active: int
    searches_total: int
    searches_enabled: int
    searches_with_error: int
    sources_total: int
    seen_jobs_total: int
    deliveries_sent: int
    deliveries_failed: int
    recent_errors: list[AdminSearchErrorRead]


class DataRequestLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    user_email: EmailStr
    request_type: str
    ip_address: str | None
    user_agent: str | None
    created_at: datetime
