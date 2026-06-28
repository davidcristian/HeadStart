"""Versioned API router aggregation."""

from fastapi import APIRouter

from app.api.v1 import auth, credentials, health, jobs, searches, sources, targets

api_router = APIRouter()
api_router.include_router(health.router, tags=["meta"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(searches.router, prefix="/searches", tags=["searches"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(targets.router, prefix="/targets", tags=["targets"])
api_router.include_router(credentials.router, prefix="/credentials", tags=["credentials"])

__all__ = ["api_router"]
