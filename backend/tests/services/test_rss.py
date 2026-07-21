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
            title="HeadStart jobs",
            link="http://testserver/api/v1/feed/rss?token=abc",
            description="Jobs discovered by your HeadStart searches.",
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
    assert '<guid isPermaLink="false">headstart:1</guid>' in xml


def test_build_rss_feed_strips_xml_invalid_control_characters() -> None:
    """Scraped C0 controls must not break strict RSS readers."""
    xml = build_rss_feed(
        RssChannel(
            title="HeadStart\x0cjobs",
            link="http://testserver/feed",
            description="Channel\x1bdesc",
            jobs=[
                _job(
                    title="Backend\x0cEngineer",
                    company="AC\x00ME",
                    location="Rem\x0bote",
                    summary="Why\x1fmatch",
                    salary="$100K",
                )
            ],
        )
    )

    assert "\x00" not in xml
    assert "\x0b" not in xml
    assert "\x0c" not in xml
    assert "\x1b" not in xml
    assert "\x1f" not in xml
    assert "<title>HeadStartjobs</title>" in xml
    assert "<description>Channeldesc</description>" in xml
    assert "<title>BackendEngineer</title>" in xml
    assert "Whymatch. ACME · Remote · $100K · new" in xml


def test_build_rss_feed_keeps_tab_lf_cr() -> None:
    xml = build_rss_feed(
        RssChannel(
            title="Head\tStart",
            link="http://testserver/feed",
            description="line1\nline2\rline3",
            jobs=[_job(title="A\tB", company="C\nD")],
        )
    )

    assert "<title>Head\tStart</title>" in xml
    assert "<description>line1\nline2\rline3</description>" in xml
    assert "<title>A\tB</title>" in xml
    assert "C\nD · Remote · new" in xml


def test_build_rss_feed_treats_naive_first_seen_as_utc() -> None:
    xml = build_rss_feed(
        RssChannel(
            title="HeadStart jobs",
            link="http://testserver/feed",
            description="Jobs",
            jobs=[_job(first_seen_at=datetime(2026, 6, 28, 12, 0))],
        )
    )

    assert "<pubDate>Sun, 28 Jun 2026 12:00:00 GMT</pubDate>" in xml
