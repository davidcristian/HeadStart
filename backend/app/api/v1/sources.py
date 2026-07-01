"""Source endpoints. Routers stay thin: parse -> service -> schema."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_verified_user
from app.models.user import User
from app.schemas.source import (
    SourceCreate,
    SourceDetectRequest,
    SourceDetectResult,
    SourceRead,
    SourceTestRequest,
    SourceTestResult,
    SourceUpdate,
)
from app.services.sources import SourceService

router = APIRouter()


@router.get("", response_model=list[SourceRead])
def list_sources(
    db: Session = Depends(get_db), user: User = Depends(get_verified_user)
) -> list[SourceRead]:
    return [SourceRead.model_validate(s) for s in SourceService(db).list_all(user.id)]


@router.post("", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
def create_source(
    data: SourceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> SourceRead:
    return SourceRead.model_validate(SourceService(db).create(user.id, data))


@router.post("/detect", response_model=SourceDetectResult)
def detect_source(
    data: SourceDetectRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> SourceDetectResult:
    """Suggest source fields from a job-board URL (browser extension helper)."""
    return SourceService(db).detect(data)


@router.get("/{source_id}", response_model=SourceRead)
def get_source(
    source_id: int, db: Session = Depends(get_db), user: User = Depends(get_verified_user)
) -> SourceRead:
    return SourceRead.model_validate(SourceService(db).get(source_id, user.id))


@router.patch("/{source_id}", response_model=SourceRead)
def update_source(
    source_id: int,
    data: SourceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> SourceRead:
    return SourceRead.model_validate(SourceService(db).update(source_id, user.id, data))


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(
    source_id: int, db: Session = Depends(get_db), user: User = Depends(get_verified_user)
) -> None:
    SourceService(db).delete(source_id, user.id)


@router.post("/{source_id}/test", response_model=SourceTestResult)
def test_source(
    source_id: int,
    data: SourceTestRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> SourceTestResult:
    """Scrape once and return sample postings without persisting or notifying."""
    return SourceService(db).test_scrape(source_id, user.id, data or SourceTestRequest())
