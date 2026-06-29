"""RSS feed endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.feed import FeedUrlRead
from app.schemas.job import JobStatus
from app.services.feed import FeedService

router = APIRouter()


def _api_base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


@router.get("/rss")
def rss_feed(
    request: Request,
    token: str = Query(min_length=1),
    search_id: int | None = Query(default=None),
    job_status: JobStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> Response:
    """Return the authenticated user's jobs as an RSS 2.0 feed."""
    service = FeedService(db)
    user = service.resolve_user(token)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired feed token.",
        )
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
    user: User = Depends(get_current_user),
) -> FeedUrlRead:
    """Return the current user's RSS feed URL."""
    service = FeedService(db)
    token = service.issue_token(user)
    url = service.build_feed_url(base_url=_api_base_url(request), token=token)
    return FeedUrlRead(url=url, token=token)


@router.post("/rotate", response_model=FeedUrlRead)
def rotate_feed_url(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedUrlRead:
    """Invalidate prior feed URLs and return a new RSS feed URL."""
    service = FeedService(db)
    token = service.rotate_token(user)
    url = service.build_feed_url(base_url=_api_base_url(request), token=token)
    return FeedUrlRead(url=url, token=token)
