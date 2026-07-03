"""Branch coverage for message-uid encoders (None + naive-datetime + parse edges)."""

from datetime import UTC, datetime

from app.inbox.fastmail_ids import fastmail_message_uid
from app.inbox.gmail_ids import gmail_message_uid, parse_internal_date, uid_to_min_received_at
from app.inbox.outlook_ids import outlook_message_uid


def test_gmail_uid_handles_none_and_naive_received_at() -> None:
    assert gmail_message_uid("id", None) > 0
    naive = datetime(2026, 6, 30, 12, 0)  # no tzinfo
    aware = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    assert gmail_message_uid("id", naive) == gmail_message_uid("id", aware)


def test_outlook_uid_handles_none_and_naive_received_at() -> None:
    assert outlook_message_uid("id", None) > 0
    naive = datetime(2026, 6, 30, 12, 0)
    aware = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    assert outlook_message_uid("id", naive) == outlook_message_uid("id", aware)


def test_fastmail_uid_handles_none_and_naive_received_at() -> None:
    assert fastmail_message_uid("id", None) > 0
    naive = datetime(2026, 6, 30, 12, 0)
    aware = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    assert fastmail_message_uid("id", naive) == fastmail_message_uid("id", aware)


def test_parse_internal_date_variants() -> None:
    # Non-str/int -> None
    assert parse_internal_date(None) is None
    assert parse_internal_date([1, 2, 3]) is None
    # Un-castable str -> None
    assert parse_internal_date("not-a-number") is None
    # Negative millis -> None
    assert parse_internal_date("-1") is None
    # Valid epoch millis -> datetime
    millis = 1_780_000_000_000
    parsed = parse_internal_date(str(millis))
    assert parsed is not None
    assert parsed == uid_to_min_received_at(millis << 20)
    # int input also works
    assert parse_internal_date(millis) == parsed
