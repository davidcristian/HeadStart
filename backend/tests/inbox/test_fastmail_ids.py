"""Tests for Fastmail message-uid encoding (overflow bounds + decode)."""

from datetime import UTC, datetime

from app.inbox.fastmail_ids import fastmail_message_uid, uid_to_min_received_at


def test_uid_stays_below_signed_bigint_for_far_future() -> None:
    """Regression: the old micros<<20 scheme produced ~71-bit uids that overflow
    a signed BigInteger column; millis<<20 must stay < 2**63."""
    uid = fastmail_message_uid("Mdeadbeef00001111", datetime(2100, 1, 1, tzinfo=UTC))
    assert uid < 2**63


def test_uid_is_monotonic_in_received_time_for_same_id() -> None:
    email_id = "Mdeadbeef00001111"
    earlier = fastmail_message_uid(email_id, datetime(2026, 1, 1, tzinfo=UTC))
    later = fastmail_message_uid(email_id, datetime(2026, 1, 2, tzinfo=UTC))
    assert later > earlier


def test_uid_to_min_received_at_is_a_lower_bound() -> None:
    received = datetime(2026, 6, 30, 12, 0, 30, tzinfo=UTC)
    decoded = uid_to_min_received_at(fastmail_message_uid("email-id", received))
    assert decoded <= received
    assert (received - decoded).total_seconds() < 1
