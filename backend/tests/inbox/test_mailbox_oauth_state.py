"""Tests for mailbox OAuth state signing and cookie binding."""

from __future__ import annotations

import pytest
from fastapi import Response

from app.api.v1.inbox_oauth_cookies import (
    MAILBOX_OAUTH_COOKIE_NAME,
    clear_mailbox_oauth_nonce_cookie,
    set_mailbox_oauth_nonce_cookie,
)
from app.core.exceptions import ValidationError
from app.inbox.mailbox_oauth_state import (
    issue_mailbox_oauth_state,
    parse_mailbox_oauth_state,
    verify_mailbox_oauth_nonce,
)


def test_issue_and_parse_mailbox_oauth_state_roundtrip() -> None:
    issued = issue_mailbox_oauth_state(user_id=42, state_type="gmail_oauth")
    user_id, nonce, code_verifier = parse_mailbox_oauth_state(
        state=issued.state,
        state_type="gmail_oauth",
        error_message="Invalid or expired Gmail OAuth state.",
    )
    assert user_id == 42
    assert nonce == issued.nonce
    assert code_verifier == issued.code_verifier
    verify_mailbox_oauth_nonce(issued.nonce, nonce)


def test_parse_mailbox_oauth_state_rejects_wrong_type() -> None:
    issued = issue_mailbox_oauth_state(user_id=1, state_type="gmail_oauth")
    with pytest.raises(ValidationError, match="Invalid or expired Gmail OAuth state"):
        parse_mailbox_oauth_state(
            state=issued.state,
            state_type="outlook_oauth",
            error_message="Invalid or expired Gmail OAuth state.",
        )


def test_parse_mailbox_oauth_state_rejects_missing_code_verifier() -> None:
    import jwt

    from app.core.config import settings

    token = jwt.encode(
        {
            "sub": "1",
            "type": "gmail_oauth",
            "nonce": "nonce-value",
            "exp": 9999999999,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(ValidationError, match="Invalid or expired Gmail OAuth state"):
        parse_mailbox_oauth_state(
            state=token,
            state_type="gmail_oauth",
            error_message="Invalid or expired Gmail OAuth state.",
        )


def test_code_challenge_s256_is_deterministic() -> None:
    from app.inbox.mailbox_oauth_state import code_challenge_s256

    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    assert code_challenge_s256(verifier) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_clear_mailbox_oauth_nonce_cookie_expires_cookie() -> None:
    response = Response()
    set_mailbox_oauth_nonce_cookie(response, "nonce-value")
    clear_mailbox_oauth_nonce_cookie(response)
    cookie_headers = [
        value.decode() for key, value in response.raw_headers if key.lower() == b"set-cookie"
    ]
    assert any(MAILBOX_OAUTH_COOKIE_NAME in header for header in cookie_headers)
    assert any(
        "max-age=0" in header.lower() or "expires=" in header.lower() for header in cookie_headers
    )
