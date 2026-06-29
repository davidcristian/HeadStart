"""Tests for RSS XML serialization."""

from datetime import UTC, datetime

from app.models.seen_job import SeenJob
from app.services.rss import RssChannel, build_rss_feed


def _job(**overrides: object) -> SeenJob:
    defaults = {
        "id": 1,
        "search_id": 10,
        "external_id": "ext-1",
        "hash": "abc",
        "title": "Backend Engineer",
        "company": "ACME",
        "location": "Remote",
        "url": "https://acme.test/jobs/1",
        "status": "new",
        "first_seen_at": datetime(2026, 6, 28, 12, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return SeenJob(**defaults)  # type: ignore[arg-type]


def test_build_rss_feed_renders_jobs() -> None:
    xml = build_rss_feed(
        RssChannel(
            title="JobNotifier jobs",
            link="http://testserver/api/v1/feed/rss?token=abc",
            description="Jobs discovered by your JobNotifier searches.",
            jobs=[_job()],
        )
    )

    assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert "<title>Backend Engineer</title>" in xml
    assert "<link>https://acme.test/jobs/1</link>" in xml
    assert "ACME · Remote · new" in xml
    assert '<guid isPermaLink="true">https://acme.test/jobs/1</guid>' in xml


def test_build_rss_feed_escapes_xml_special_characters() -> None:
    xml = build_rss_feed(
        RssChannel(
            title='Jobs & "Alerts"',
            link="http://testserver/feed",
            description="Test <feed>",
            jobs=[_job(title="Dev & Ops", company="A <B>", location="", url="")],
        )
    )

    assert "<title>Dev &amp; Ops</title>" in xml
    assert "<title>Jobs &amp; " in xml
    assert "<description>Test &lt;feed&gt;</description>" in xml
    assert '<guid isPermaLink="false">jobnotifier:1</guid>' in xml
