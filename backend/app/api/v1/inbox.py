"""Dev-only mailbox credential and connectivity endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_verified_user
from app.inbox.types import FetchResult
from app.models.user import User
from app.schemas.mailbox import (
    MailboxCredentialRead,
    MailboxCredentialUpsert,
    MailboxTestRequest,
    MailboxTestResponse,
)
from app.services.inbox import InboxService

router = APIRouter()


@router.get("/credentials", response_model=MailboxCredentialRead)
def get_mailbox_credentials(
    db: Session = Depends(get_db), user: User = Depends(get_verified_user)
) -> MailboxCredentialRead:
    InboxService(db).require_enabled()
    return InboxService(db).get_read(user.id)


@router.put("/credentials", response_model=MailboxCredentialRead)
def upsert_mailbox_credentials(
    data: MailboxCredentialUpsert,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> MailboxCredentialRead:
    return InboxService(db).upsert(user.id, data)


@router.delete("/credentials", status_code=status.HTTP_204_NO_CONTENT)
def delete_mailbox_credentials(
    db: Session = Depends(get_db), user: User = Depends(get_verified_user)
) -> None:
    InboxService(db).delete(user.id)


@router.post("/test", response_model=MailboxTestResponse)
def test_mailbox_connection(
    data: MailboxTestRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> MailboxTestResponse:
    config = data.config if data else None
    return InboxService(db).test_connection(user.id, config=config)


@router.get("/messages", response_model=FetchResult)
def fetch_mailbox_messages(
    since_uid: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> FetchResult:
    """Fetch inbound messages (dev tooling; classification lands in Phase 20c follow-ups)."""
    bounded_limit = min(max(limit, 1), 100)
    return InboxService(db).fetch_messages(user.id, since_uid=since_uid, limit=bounded_limit)
