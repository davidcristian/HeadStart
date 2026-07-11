import json

import httpx
import pytest

from app.reply_drafters.adapters.gemini import GeminiReplyDrafter
from app.reply_drafters.types import ReplyDraftContext
from app.schemas.profile import ProfileData


class _Settings:
    gemini_api_key = "gemini-test-key"
    gemini_model = "gemini-2.0-flash"
    gemini_base_url = "https://generativelanguage.googleapis.fixture.test/v1beta"
    email_draft_max_tokens = 600


def _gemini_response(text: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"candidates": [{"content": {"parts": [{"text": text}], "role": "model"}}]},
    )


def test_gemini_reply_drafter_sends_key_in_header_not_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-key"] == "gemini-test-key"
        assert "key=" not in str(request.url)
        return _gemini_response(json.dumps({"subject": "Re: hi", "body": "Thanks!", "notes": ""}))

    drafter = GeminiReplyDrafter(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_Settings(),
    )

    result = drafter.draft(ReplyDraftContext(profile=ProfileData()))
    assert result.body == "Thanks!"


def test_gemini_reply_drafter_requires_api_key() -> None:
    class _NoKey(_Settings):
        gemini_api_key = ""

    drafter = GeminiReplyDrafter(client=httpx.Client(), settings=_NoKey())
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        drafter.draft(ReplyDraftContext(profile=ProfileData()))


def test_gemini_reply_drafter_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    drafter = GeminiReplyDrafter(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_Settings(),
    )
    with pytest.raises(httpx.HTTPError):
        drafter.draft(ReplyDraftContext(profile=ProfileData()))


def test_gemini_reply_drafter_close_behaviour() -> None:
    drafter = GeminiReplyDrafter(settings=_Settings())
    drafter.close()
    assert drafter._client.is_closed

    client = httpx.Client()
    injected = GeminiReplyDrafter(client=client, settings=_Settings())
    injected.close()
    assert not client.is_closed
    client.close()
