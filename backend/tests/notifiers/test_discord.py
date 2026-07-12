import json

import httpx
import pytest

from app.notifiers import NotifyContext, get_notifier
from app.notifiers.adapters.discord import DiscordNotifier
from app.scrapers.types import JobPosting


def _job(external_id: str = "1") -> JobPosting:
    return JobPosting(
        external_id=external_id,
        title="Software Engineer",
        company="Google",
        location="Amsterdam",
        url="https://careers.example/jobs/1",
    )


def test_discord_posts_expected_payload() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        assert str(request.url) == "https://discord.fixture.test/api/webhooks/123/secret"
        assert request.headers["host"] == "discord.fixture.test"
        return httpx.Response(204)

    notifier = DiscordNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="discord",
        config={"webhook_url": "https://discord.fixture.test/api/webhooks/123/secret"},
    )

    results = notifier.send(ctx, [_job()])

    assert len(results) == 1
    assert results[0].status == "sent"
    embed = captured[0]["embeds"][0]
    assert embed["title"] == "Software Engineer @ Google"
    assert "Google" in embed["description"]
    assert "Amsterdam" in embed["description"]
    assert embed["url"] == "https://careers.example/jobs/1"
    assert embed["color"] == 0x5865F2


def test_discord_records_failure_without_raising() -> None:
    secret_url = "https://discord.fixture.test/api/webhooks/123/secret"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    notifier = DiscordNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="discord",
        config={"webhook_url": secret_url},
    )

    results = notifier.send(ctx, [_job(), _job("2")])

    assert [r.status for r in results] == ["failed", "failed"]
    assert results[0].error
    assert secret_url not in (results[0].error or "")
    assert "[REDACTED]" in (results[0].error or "")


def test_discord_requires_webhook_url() -> None:
    notifier = DiscordNotifier(client=httpx.Client())
    ctx = NotifyContext(target_type="discord", config={})

    try:
        notifier.send(ctx, [_job()])
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "webhook_url" in str(exc)


def test_discord_rejects_unsafe_url() -> None:
    notifier = DiscordNotifier(client=httpx.Client())
    ctx = NotifyContext(
        target_type="discord",
        config={"webhook_url": "http://127.0.0.1/hook"},
    )
    with pytest.raises(ValueError, match="not allowed|disallowed"):
        notifier.send(ctx, [_job()])


def test_discord_single_includes_summary_in_description() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(204)

    notifier = DiscordNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="discord",
        config={"webhook_url": "https://discord.fixture.test/api/webhooks/123/secret"},
    )
    job = _job()
    job.summary = "strong python match"
    notifier.send(ctx, [job])
    assert "strong python match" in captured[0]["embeds"][0]["description"]


def test_discord_payload_minimal_job_has_no_description_or_url() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(204)

    notifier = DiscordNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="discord",
        config={"webhook_url": "https://discord.fixture.test/api/webhooks/123/secret"},
    )
    # Title only: no company/summary/location/url means no description or url keys.
    notifier.send(ctx, [JobPosting(external_id="1", title="")])
    embed = captured[0]["embeds"][0]
    assert embed["title"] == "New job"
    assert "description" not in embed
    assert "url" not in embed


def test_discord_digest_sends_single_message() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(204)

    notifier = DiscordNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="discord",
        config={"webhook_url": "https://discord.fixture.test/api/webhooks/123/secret"},
        digest=True,
        search_name="Backend",
    )
    job = _job()
    job.summary = "great match"
    no_url = JobPosting(external_id="2", title="Data Scientist", company="ACME")
    results = notifier.send(ctx, [job, no_url])

    assert len(results) == 2
    assert all(r.status == "sent" for r in results)
    assert len(captured) == 1
    embed = captured[0]["embeds"][0]
    assert embed["title"] == "2 new jobs — Backend"
    assert "great match" in embed["description"]
    link = "[Software Engineer @ Google (Amsterdam)](https://careers.example/jobs/1)"
    assert link in embed["description"]
    assert "• Data Scientist @ ACME" in embed["description"]


def test_discord_digest_empty_jobs_returns_empty() -> None:
    notifier = DiscordNotifier(client=httpx.Client())
    ctx = NotifyContext(
        target_type="discord",
        config={"webhook_url": "https://discord.fixture.test/api/webhooks/123/secret"},
        digest=True,
    )
    assert notifier.send(ctx, []) == []


def test_discord_digest_records_failure() -> None:
    secret_url = "https://discord.fixture.test/api/webhooks/123/secret"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    notifier = DiscordNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="discord",
        config={"webhook_url": secret_url},
        digest=True,
    )
    results = notifier.send(ctx, [_job(), _job("2")])
    assert [r.status for r in results] == ["failed", "failed"]
    assert results[0].error
    assert secret_url not in (results[0].error or "")
    assert "[REDACTED]" in (results[0].error or "")


def test_discord_close_behaviour() -> None:
    notifier = DiscordNotifier()
    notifier.close()
    assert notifier._client.is_closed

    client = httpx.Client()
    injected = DiscordNotifier(client=client)
    injected.close()
    assert not client.is_closed
    client.close()


def test_discord_escapes_poisoned_title_and_summary() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(204)

    notifier = DiscordNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="discord",
        config={"webhook_url": "https://discord.fixture.test/api/webhooks/123/secret"},
    )
    job = JobPosting(
        external_id="1",
        title="[Click](https://evil.tld)",
        company="Acme",
        summary="See [here](https://evil.tld)",
        url="https://careers.example/jobs/1",
    )
    notifier.send(ctx, [job])
    embed = captured[0]["embeds"][0]
    assert "[Click](https://evil.tld)" not in embed["title"]
    assert "Click(https://evil.tld)" in embed["title"]
    assert "here(https://evil.tld)" in embed["description"]
    assert embed["url"] == "https://careers.example/jobs/1"


def test_discord_omits_embed_url_for_non_http() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(204)

    notifier = DiscordNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="discord",
        config={"webhook_url": "https://discord.fixture.test/api/webhooks/123/secret"},
    )
    notifier.send(
        ctx,
        [JobPosting(external_id="1", title="Engineer", url="javascript:alert(1)")],
    )
    embed = captured[0]["embeds"][0]
    assert "url" not in embed
    assert "javascript:" not in str(embed)


def test_discord_digest_escapes_poisoned_fields_and_skips_bad_urls() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(204)

    notifier = DiscordNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="discord",
        config={"webhook_url": "https://discord.fixture.test/api/webhooks/123/secret"},
        digest=True,
        search_name="Backend [roles]",
    )
    poisoned = JobPosting(
        external_id="1",
        title="[phish](https://evil.tld)",
        company="ACME",
        summary="[click](https://evil.tld)",
        url="javascript:alert(1)",
    )
    good = _job("2")
    notifier.send(ctx, [poisoned, good])
    embed = captured[0]["embeds"][0]
    assert "Backend roles" in embed["title"]
    assert "[" not in embed["title"]
    assert "[phish](https://evil.tld)" not in embed["description"]
    assert "javascript:" not in embed["description"]
    assert "phish(https://evil.tld)" in embed["description"]
    assert "click(https://evil.tld)" in embed["description"]
    link = "[Software Engineer @ Google (Amsterdam)](https://careers.example/jobs/1)"
    assert link in embed["description"]


def test_registry_resolves_discord() -> None:
    assert isinstance(get_notifier("discord"), DiscordNotifier)
