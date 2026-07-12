"""RSS feed endpoints."""

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_verified_user
from app.core.exceptions import UnauthorizedError
from app.models.user import User
from app.schemas.feed import FeedUrlRead
from app.schemas.job import JobStatus
from app.services.feed import FeedService
from app.services.plan_limits import PlanLimitsService

router = APIRouter()


def _api_base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def _resolve_feed_token(
    request: Request,
    token: str | None = Query(default=None, min_length=1),
) -> str:
    """Prefer ?token= (RSS readers); fall back to Authorization: Bearer."""
    if token is not None:
        return token
    authorization = request.headers.get("Authorization")
    if authorization is not None:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and value.strip():
            return value.strip()
    raise UnauthorizedError("Missing feed token.")


@router.get("/rss")
def rss_feed(
    request: Request,
    token: str = Depends(_resolve_feed_token),
    search_id: int | None = Query(default=None),
    job_status: JobStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> Response:
    """Return the authenticated user's jobs as an RSS 2.0 feed."""
    service = FeedService(db)
    user = service.resolve_user(token)
    if user is None:
        raise UnauthorizedError("Invalid or expired feed token.")
    PlanLimitsService(db).require_rss_feed(user)
    feed_url = service.build_feed_url(
        base_url=_api_base_url(request),
        token=token,
        search_id=search_id,
        status=job_status,
    )
    body = service.render_rss(
        user,
        feed_url=feed_url,
        search_id=search_id,
        status=job_status,
        limit=limit,
    )
    return Response(content=body, media_type="application/rss+xml")


@router.get("/url", response_model=FeedUrlRead)
def feed_url(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> FeedUrlRead:
    """Return the current user's RSS feed URL."""
    PlanLimitsService(db).require_rss_feed(user)
    service = FeedService(db)
    token = service.issue_token(user)
    url = service.build_feed_url(base_url=_api_base_url(request), token=token)
    return FeedUrlRead(url=url, token=token)


@router.post("/rotate", response_model=FeedUrlRead)
def rotate_feed_url(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> FeedUrlRead:
    """Invalidate prior feed URLs and return a new RSS feed URL."""
    PlanLimitsService(db).require_rss_feed(user)
    service = FeedService(db)
    token = service.rotate_token(user)
    url = service.build_feed_url(base_url=_api_base_url(request), token=token)
    return FeedUrlRead(url=url, token=token)
