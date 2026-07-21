import json
from urllib.parse import urlparse

import httpx
import pytest

from app.notifiers import NotifyContext, get_notifier
from app.notifiers.adapters.telegram import TelegramNotifier
from app.scrapers.types import JobPosting


@pytest.fixture(autouse=True)
def _skip_live_dns_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep telegram unit tests offline: pin without rewriting to a resolved IP."""

    def _identity(url: str) -> object:
        host = urlparse(url).hostname or ""
        return type("Pinned", (), {"request_url": url, "host_header": host})()

    monkeypatch.setattr("app.core.outbound_http.pin_outbound_request", _identity)


def _job(external_id: str = "1") -> JobPosting:
    return JobPosting(
        external_id=external_id,
        title="Software Engineer",
        company="Google",
        location="Amsterdam",
        url="https://careers.example/jobs/1",
    )


def test_telegram_posts_expected_payload() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        assert str(request.url) == "https://api.telegram.org/bottest-token/sendMessage"
        return httpx.Response(200, json={"ok": True})

    notifier = TelegramNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="telegram",
        config={"bot_token": "test-token", "chat_id": "123456789"},
    )

    results = notifier.send(ctx, [_job()])

    assert len(results) == 1
    assert results[0].status == "sent"
    body = captured[0]
    assert body["chat_id"] == "123456789"
    assert body["parse_mode"] == "HTML"
    assert "<b>Software Engineer</b> @ Google" in body["text"]
    assert "Amsterdam" in body["text"]
    assert 'href="https://careers.example/jobs/1"' in body["text"]


def test_telegram_escapes_html_in_job_fields() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True})

    job = JobPosting(
        external_id="x",
        title="Dev &amp; Ops",
        company="<Corp>",
        location="A < B",
        url="https://example.com/?a=1&b=2",
    )
    notifier = TelegramNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="telegram",
        config={"bot_token": "test-token", "chat_id": "1"},
    )

    notifier.send(ctx, [job])

    text = captured[0]["text"]
    assert "<Corp>" not in text
    assert "&lt;Corp&gt;" in text
    assert "A &lt; B" in text


def test_telegram_records_failure_without_raising() -> None:
    secret = "123456:SECRET-BOT-TOKEN"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"ok": False, "description": "bad chat"})

    notifier = TelegramNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="telegram",
        config={"bot_token": secret, "chat_id": "123456789"},
    )

    results = notifier.send(ctx, [_job(), _job("2")])

    assert [r.status for r in results] == ["failed", "failed"]
    assert results[0].error
    assert secret not in (results[0].error or "")
    assert "[REDACTED]" in (results[0].error or "")


def test_telegram_safe_http_error_redacts_bot_token() -> None:
    from app.notifiers.http_errors import safe_http_error

    secret = "999:LEAK-ME"
    request = httpx.Request("POST", f"https://api.telegram.org/bot{secret}/sendMessage")
    response = httpx.Response(401, request=request)
    with pytest.raises(httpx.HTTPStatusError) as raised:
        response.raise_for_status()
    raw = str(raised.value)
    safe = safe_http_error(raised.value, secret)
    assert secret in raw
    assert secret not in safe
    assert "[REDACTED]" in safe
    assert safe_http_error(ValueError("no url"), secret) == "no url"
    assert safe_http_error(ValueError("plain"), "") == "plain"


def test_telegram_requires_bot_token_and_chat_id() -> None:
    notifier = TelegramNotifier(client=httpx.Client())

    try:
        notifier.send(NotifyContext(target_type="telegram", config={"chat_id": "1"}), [_job()])
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "bot_token" in str(exc)

    try:
        notifier.send(NotifyContext(target_type="telegram", config={"bot_token": "t"}), [_job()])
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "chat_id" in str(exc)


def test_telegram_single_includes_summary_line() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True})

    notifier = TelegramNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(target_type="telegram", config={"bot_token": "t", "chat_id": "1"})
    job = _job()
    job.summary = "strong python match"
    notifier.send(ctx, [job])
    assert "strong python match" in captured[0]["text"]


def test_telegram_text_omits_absent_fields() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True})

    notifier = TelegramNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="telegram",
        config={"bot_token": "t", "chat_id": "1"},
    )
    job = JobPosting(external_id="1", title="")
    notifier.send(ctx, [job])

    text = captured[0]["text"]
    assert "<b>New job</b>" in text
    assert "@" not in text
    assert "Apply" not in text


def test_telegram_digest_sends_single_message() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True})

    notifier = TelegramNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="telegram",
        config={"bot_token": "t", "chat_id": "1"},
        digest=True,
        search_name="Backend",
    )
    job = _job()
    job.summary = "why it matches"
    # Second job has no url so the digest block skips the Apply link.
    no_url = JobPosting(external_id="2", title="Data Scientist", company="ACME")
    results = notifier.send(ctx, [job, no_url])

    assert len(results) == 2
    assert all(r.status == "sent" for r in results)
    assert len(captured) == 1
    text = captured[0]["text"]
    assert "2 new jobs for Backend" in text
    assert "why it matches" in text
    assert "Apply" in text


def test_telegram_digest_empty_jobs_returns_empty() -> None:
    notifier = TelegramNotifier(client=httpx.Client())
    ctx = NotifyContext(
        target_type="telegram",
        config={"bot_token": "t", "chat_id": "1"},
        digest=True,
    )
    assert notifier.send(ctx, []) == []


def test_telegram_digest_records_failure() -> None:
    secret = "digest:SECRET-TOKEN"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    notifier = TelegramNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="telegram",
        config={"bot_token": secret, "chat_id": "1"},
        digest=True,
    )
    results = notifier.send(ctx, [_job(), _job("2")])
    assert [r.status for r in results] == ["failed", "failed"]
    assert results[0].error
    assert secret not in (results[0].error or "")
    assert "[REDACTED]" in (results[0].error or "")


def test_telegram_text_rejects_non_http_apply_url() -> None:
    # Bypass ingest validation to assert render-side scheme gating.
    job = JobPosting.model_construct(
        external_id="1",
        title="Engineer",
        company="ACME",
        location="",
        url="javascript:alert(1)",
        summary="",
        raw={},
    )
    text = TelegramNotifier._text(job)
    assert "Apply" not in text
    assert "javascript:" not in text


def test_telegram_digest_rejects_non_http_apply_url() -> None:
    job = JobPosting.model_construct(
        external_id="1",
        title="Engineer",
        company="ACME",
        location="",
        url="javascript:alert(1)",
        summary="match",
        raw={},
    )
    payload = TelegramNotifier._digest_payload(
        "1",
        NotifyContext(target_type="telegram", config={}, digest=True, search_name="S"),
        [job],
    )
    assert "Apply" not in payload["text"]
    assert "javascript:" not in payload["text"]


def test_telegram_close_behaviour() -> None:
    notifier = TelegramNotifier()
    notifier.close()
    assert notifier._client.is_closed

    client = httpx.Client()
    injected = TelegramNotifier(client=client)
    injected.close()
    assert not client.is_closed
    client.close()


def test_registry_resolves_telegram() -> None:
    assert isinstance(get_notifier("telegram"), TelegramNotifier)
