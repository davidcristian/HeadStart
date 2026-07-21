"""Build Settings redirects for mailbox OAuth callback outcomes."""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import status
from fastapi.responses import RedirectResponse

from app.api.v1.inbox_oauth_cookies import clear_mailbox_oauth_nonce_cookie
from app.core.config import settings


def mailbox_oauth_settings_redirect(
    mailbox: str,
    *,
    reason: str | None = None,
) -> RedirectResponse:
    """302 to Settings with URL-encoded mailbox/reason query params."""
    settings_url = f"{settings.frontend_base_url.rstrip('/')}/app/settings"
    params: dict[str, str] = {"mailbox": mailbox}
    if reason is not None:
        params["reason"] = reason
    redirect = RedirectResponse(
        url=f"{settings_url}?{urlencode(params)}",
        status_code=status.HTTP_302_FOUND,
    )
    clear_mailbox_oauth_nonce_cookie(redirect)
    return redirect
