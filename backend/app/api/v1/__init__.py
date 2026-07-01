"""Versioned API router aggregation."""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    application_logs,
    auth,
    billing,
    credentials,
    feed,
    health,
    jobs,
    portals,
    profile,
    searches,
    sources,
    targets,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["meta"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(portals.router, prefix="/portals", tags=["portals"])
api_router.include_router(searches.router, prefix="/searches", tags=["searches"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(
    application_logs.router, prefix="/application-logs", tags=["application-logs"]
)
api_router.include_router(feed.router, prefix="/feed", tags=["feed"])
api_router.include_router(targets.router, prefix="/targets", tags=["targets"])
api_router.include_router(credentials.router, prefix="/credentials", tags=["credentials"])
api_router.include_router(profile.router, prefix="/profile", tags=["profile"])

__all__ = ["api_router"]
