"""Dev-only mailbox credential, connectivity, and classification endpoints."""

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_verified_user
from app.core.config import settings
from app.core.exceptions import ValidationError
from app.inbox.types import FetchResult
from app.models.user import User
from app.schemas.inbox_classification import (
    EmailClassificationListParams,
    EmailClassificationRead,
    EmailClassifyRequest,
)
from app.schemas.inbox_reply_draft import ReplyDraftListParams, ReplyDraftRead, ReplyDraftRequest
from app.schemas.inbox_reply_send_log import ReplySendLogListParams, ReplySendLogRead
from app.schemas.inbox_routing import (
    InboxRouteRequest,
    InboxRouteResponse,
    InboxRoutingConfigRead,
    InboxRoutingConfigUpdate,
)
from app.schemas.mailbox import (
    GmailAuthorizeResponse,
    MailboxCredentialRead,
    MailboxCredentialUpsert,
    MailboxTestRequest,
    MailboxTestResponse,
    OutlookAuthorizeResponse,
    YahooAuthorizeResponse,
)
from app.services.email_classification import EmailClassificationService
from app.services.inbox import InboxService
from app.services.inbox_routing import InboxRoutingService
from app.services.reply_drafts import ReplyDraftService
from app.services.reply_safe_send import ReplySafeSendService

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


@router.get("/gmail/authorize", response_model=GmailAuthorizeResponse)
def gmail_authorize(
    db: Session = Depends(get_db), user: User = Depends(get_verified_user)
) -> GmailAuthorizeResponse:
    """Return a Google OAuth URL to connect Gmail for inbox automation."""
    return InboxService(db).gmail_authorize_url(user.id)


@router.get("/gmail/callback")
def gmail_oauth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """OAuth redirect target — stores encrypted Gmail tokens and returns to Settings."""
    settings_url = f"{settings.frontend_base_url.rstrip('/')}/app/settings"
    if error:
        return RedirectResponse(
            url=f"{settings_url}?mailbox=gmail_error&reason={error}",
            status_code=status.HTTP_302_FOUND,
        )
    if not code or not state:
        return RedirectResponse(
            url=f"{settings_url}?mailbox=gmail_error&reason=missing_code",
            status_code=status.HTTP_302_FOUND,
        )
    try:
        InboxService(db).complete_gmail_oauth(code=code, state=state)
    except ValidationError:
        return RedirectResponse(
            url=f"{settings_url}?mailbox=gmail_error",
            status_code=status.HTTP_302_FOUND,
        )
    return RedirectResponse(
        url=f"{settings_url}?mailbox=gmail_connected",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/outlook/authorize", response_model=OutlookAuthorizeResponse)
def outlook_authorize(
    db: Session = Depends(get_db), user: User = Depends(get_verified_user)
) -> OutlookAuthorizeResponse:
    """Return a Microsoft OAuth URL to connect Outlook for inbox automation."""
    return InboxService(db).outlook_authorize_url(user.id)


@router.get("/outlook/callback")
def outlook_oauth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """OAuth redirect target — stores encrypted Outlook tokens and returns to Settings."""
    settings_url = f"{settings.frontend_base_url.rstrip('/')}/app/settings"
    if error:
        return RedirectResponse(
            url=f"{settings_url}?mailbox=outlook_error&reason={error}",
            status_code=status.HTTP_302_FOUND,
        )
    if not code or not state:
        return RedirectResponse(
            url=f"{settings_url}?mailbox=outlook_error&reason=missing_code",
            status_code=status.HTTP_302_FOUND,
        )
    try:
        InboxService(db).complete_outlook_oauth(code=code, state=state)
    except ValidationError:
        return RedirectResponse(
            url=f"{settings_url}?mailbox=outlook_error",
            status_code=status.HTTP_302_FOUND,
        )
    return RedirectResponse(
        url=f"{settings_url}?mailbox=outlook_connected",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/yahoo/authorize", response_model=YahooAuthorizeResponse)
def yahoo_authorize(
    db: Session = Depends(get_db), user: User = Depends(get_verified_user)
) -> YahooAuthorizeResponse:
    """Return a Yahoo OAuth URL to connect Yahoo Mail for inbox automation."""
    return InboxService(db).yahoo_authorize_url(user.id)


@router.get("/yahoo/callback")
def yahoo_oauth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """OAuth redirect target — stores encrypted Yahoo tokens and returns to Settings."""
    settings_url = f"{settings.frontend_base_url.rstrip('/')}/app/settings"
    if error:
        return RedirectResponse(
            url=f"{settings_url}?mailbox=yahoo_error&reason={error}",
            status_code=status.HTTP_302_FOUND,
        )
    if not code or not state:
        return RedirectResponse(
            url=f"{settings_url}?mailbox=yahoo_error&reason=missing_code",
            status_code=status.HTTP_302_FOUND,
        )
    try:
        InboxService(db).complete_yahoo_oauth(code=code, state=state)
    except ValidationError:
        return RedirectResponse(
            url=f"{settings_url}?mailbox=yahoo_error",
            status_code=status.HTTP_302_FOUND,
        )
    return RedirectResponse(
        url=f"{settings_url}?mailbox=yahoo_connected",
        status_code=status.HTTP_302_FOUND,
    )


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
    """Fetch inbound messages from the configured mailbox."""
    bounded_limit = min(max(limit, 1), 100)
    return InboxService(db).fetch_messages(user.id, since_uid=since_uid, limit=bounded_limit)


@router.post("/classify", response_model=EmailClassificationRead)
def classify_inbox_message(
    data: EmailClassifyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> EmailClassificationRead:
    """Classify one inbound message and link it to a known application when possible."""
    return EmailClassificationService(db).classify(user.id, data)


@router.get("/classifications", response_model=list[EmailClassificationRead])
def list_inbox_classifications(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> list[EmailClassificationRead]:
    """List recent persisted email classifications for the current user."""
    params = EmailClassificationListParams(limit=limit)
    return EmailClassificationService(db).list_for_user(user.id, limit=params.limit)


@router.get("/routing", response_model=InboxRoutingConfigRead)
def get_inbox_routing_config(
    db: Session = Depends(get_db), user: User = Depends(get_verified_user)
) -> InboxRoutingConfigRead:
    """Read label→folder routing settings for the mailbox."""
    return InboxRoutingService(db).get_config(user.id)


@router.put("/routing", response_model=InboxRoutingConfigRead)
def update_inbox_routing_config(
    data: InboxRoutingConfigUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> InboxRoutingConfigRead:
    """Update label→folder routing settings."""
    return InboxRoutingService(db).update_config(user.id, data)


@router.post("/route", response_model=InboxRouteResponse)
def route_inbox_message(
    data: InboxRouteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> InboxRouteResponse:
    """Move a classified message into its configured IMAP folder."""
    return InboxRoutingService(db).route_by_request(user.id, data)


@router.post("/draft-reply", response_model=ReplyDraftRead)
def draft_inbox_reply(
    data: ReplyDraftRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> ReplyDraftRead:
    """Draft a recruiter follow-up reply for one classified message (dry-run only)."""
    return ReplyDraftService(db).draft(user.id, data)


@router.get("/reply-drafts", response_model=list[ReplyDraftRead])
def list_inbox_reply_drafts(
    seen_job_id: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> list[ReplyDraftRead]:
    """List persisted reply drafts for the current user."""
    params = ReplyDraftListParams(seen_job_id=seen_job_id, limit=limit)
    return ReplyDraftService(db).list_for_user(
        user.id, seen_job_id=params.seen_job_id, limit=params.limit
    )


@router.get("/reply-send-logs", response_model=list[ReplySendLogRead])
def list_inbox_reply_send_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> list[ReplySendLogRead]:
    """List audit rows for autonomous recruiter reply decisions."""
    InboxService(db).require_enabled()
    params = ReplySendLogListParams(limit=limit)
    rows = ReplySafeSendService(db).list_for_user(user.id, limit=params.limit)
    return [ReplySendLogRead.model_validate(row) for row in rows]
