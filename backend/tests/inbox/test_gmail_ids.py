"""Tests for Gmail message-uid encoding (time-ordered + overflow bounds)."""

from datetime import UTC, datetime

from app.inbox.gmail_ids import gmail_message_uid, uid_to_min_received_at


def test_uid_is_time_ordered_not_id_ordered() -> None:
    # Later received time -> larger uid, even when the raw id sorts the other way.
    earlier = gmail_message_uid("ffffffffffffffff", datetime(2026, 1, 1, tzinfo=UTC))
    later = gmail_message_uid("0000000000000001", datetime(2026, 6, 1, tzinfo=UTC))
    assert later > earlier


def test_uid_stays_below_signed_bigint_for_far_future() -> None:
    uid = gmail_message_uid("18c5f2a3b4d6e7f8", datetime(2100, 1, 1, tzinfo=UTC))
    assert uid < 2**63


def test_uid_to_min_received_at_is_a_lower_bound() -> None:
    received = datetime(2026, 6, 30, 12, 0, 30, tzinfo=UTC)
    decoded = uid_to_min_received_at(gmail_message_uid("gmail-id", received))
    assert decoded <= received
    assert (received - decoded).total_seconds() < 1
