"""Tests for lenient scraper date helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from app.scrapers.dates import parse_epoch_millis, parse_epoch_seconds, parse_iso8601


def test_parse_iso8601_valid_and_invalid() -> None:
    assert parse_iso8601("2026-05-01T12:00:00Z") == datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    assert parse_iso8601("") is None
    assert parse_iso8601(None) is None
    assert parse_iso8601(123) is None
    assert parse_iso8601("not-a-date") is None


def test_parse_epoch_seconds_valid() -> None:
    result = parse_epoch_seconds(1766750430)
    assert result == datetime.fromtimestamp(1766750430, tz=UTC)


def test_parse_epoch_seconds_rejects_non_numeric() -> None:
    assert parse_epoch_seconds(None) is None
    assert parse_epoch_seconds("1766750430") is None
    assert parse_epoch_seconds(True) is None


def test_parse_epoch_seconds_overflow_returns_none() -> None:
    """Hostile epochs must degrade to None instead of raising."""
    assert parse_epoch_seconds(1e30) is None
    assert parse_epoch_seconds(1e20) is None
    assert parse_epoch_seconds(-1e20) is None
    assert parse_epoch_seconds(float("inf")) is None
    assert parse_epoch_seconds(float("nan")) is None


def test_parse_epoch_millis_valid() -> None:
    result = parse_epoch_millis(1700000000000)
    assert result == datetime.fromtimestamp(1700000000.0, tz=UTC)


def test_parse_epoch_millis_overflow_returns_none() -> None:
    assert parse_epoch_millis(1e30) is None
    assert parse_epoch_millis(float("inf")) is None
    assert parse_epoch_millis(True) is None
