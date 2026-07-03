"""Tests for Gmail message id uid mapping."""

from app.inbox.gmail_ids import gmail_id_to_uid, uid_to_gmail_id


def test_gmail_id_round_trip() -> None:
    gmail_id = "18c5f2a3b4d6e7f8"
    uid = gmail_id_to_uid(gmail_id)
    assert uid_to_gmail_id(uid) == gmail_id


def test_gmail_id_normalizes_case() -> None:
    assert gmail_id_to_uid("AbCd") == gmail_id_to_uid("abcd")
