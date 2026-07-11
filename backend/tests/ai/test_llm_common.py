from types import SimpleNamespace

import httpx
import pytest

from app.ai.llm_common import (
    auth_headers,
    extract_anthropic_content,
    extract_gemini_content,
    extract_openai_content,
    gemini_headers,
    gemini_url,
    llm_post,
)
from app.core.outbound_url import UnsafeOutboundUrlError


def test_extract_openai_content_happy_and_strips() -> None:
    data = {"choices": [{"message": {"content": "  hi there  "}}]}
    assert extract_openai_content(data) == "hi there"


def test_extract_openai_content_none_becomes_empty() -> None:
    assert extract_openai_content({"choices": [{"message": {"content": None}}]}) == ""


def test_extract_openai_content_bad_shape_raises() -> None:
    with pytest.raises(ValueError, match="unexpected OpenAI response shape"):
        extract_openai_content({"choices": []})


def test_extract_gemini_content_happy() -> None:
    data = {"candidates": [{"content": {"parts": [{"text": " blurb "}]}}]}
    assert extract_gemini_content(data) == "blurb"


def test_extract_gemini_content_bad_shape_raises() -> None:
    with pytest.raises(ValueError, match="unexpected Gemini response shape"):
        extract_gemini_content({"candidates": [{}]})


def test_extract_anthropic_content_happy() -> None:
    assert extract_anthropic_content({"content": [{"text": " ok "}]}) == "ok"


def test_extract_anthropic_content_bad_shape_raises() -> None:
    with pytest.raises(ValueError, match="unexpected Anthropic response shape"):
        extract_anthropic_content({"content": []})


def test_auth_headers_with_key() -> None:
    assert auth_headers("  sk-abc ") == {"Authorization": "Bearer sk-abc"}


def test_auth_headers_empty_key_is_no_header() -> None:
    assert auth_headers("   ") == {}


def test_gemini_url_rstrips_base_and_quotes_model() -> None:
    url = gemini_url("https://host/v1beta/", "models/x y")
    assert url == "https://host/v1beta/models/models%2Fx%20y:generateContent"


def test_gemini_url_plain_model() -> None:
    url = gemini_url("https://host/v1beta", "gemini-2.0-flash")
    assert url == "https://host/v1beta/models/gemini-2.0-flash:generateContent"


def test_gemini_headers_uses_google_header_and_strips() -> None:
    assert gemini_headers("  key-123 ") == {"x-goog-api-key": "key-123"}


def test_llm_post_pins_public_fixture_host() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"ok": True})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    resp = llm_post(
        client,
        "https://api.openai.fixture.test/v1/chat/completions",
        json={"model": "x"},
    )
    assert resp.status_code == 200
    assert str(captured[0].url) == "https://api.openai.fixture.test/v1/chat/completions"
    assert captured[0].headers["Host"] == "api.openai.fixture.test"


def test_llm_post_rejects_private_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.ai.llm_common.get_settings",
        lambda: SimpleNamespace(environment="production"),
    )
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    with pytest.raises(UnsafeOutboundUrlError):
        llm_post(client, "http://127.0.0.1:8080/v1/chat/completions", json={})


def test_llm_post_allows_loopback_in_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.ai.llm_common.get_settings",
        lambda: SimpleNamespace(environment="local"),
    )
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"ok": True})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    resp = llm_post(client, "http://localhost:8080/v1/chat/completions", json={})
    assert resp.status_code == 200
    assert str(captured[0].url) == "http://localhost:8080/v1/chat/completions"
