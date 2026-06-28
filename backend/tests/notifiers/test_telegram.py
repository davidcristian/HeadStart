import json

import httpx

from app.notifiers import NotifyContext, get_notifier
from app.notifiers.adapters.telegram import TelegramNotifier
from app.scrapers.types import JobPosting


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
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"ok": False, "description": "bad chat"})

    notifier = TelegramNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="telegram",
        config={"bot_token": "test-token", "chat_id": "123456789"},
    )

    results = notifier.send(ctx, [_job(), _job("2")])

    assert [r.status for r in results] == ["failed", "failed"]
    assert results[0].error


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


def test_registry_resolves_telegram() -> None:
    assert isinstance(get_notifier("telegram"), TelegramNotifier)
