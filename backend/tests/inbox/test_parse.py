"""Tests for RFC 822 parsing helpers."""

from pathlib import Path

from app.inbox.parse import parse_rfc822

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_parse_rfc822_extracts_headers_and_body() -> None:
    raw = (FIXTURES / "inbox_sample.eml").read_bytes()
    message = parse_rfc822(uid=42, raw_bytes=raw)
    assert message.uid == 42
    assert message.from_addr == "recruiter@acme.example"
    assert message.to_addrs == ["candidate@example.com"]
    assert message.subject == "Re: Software Engineer application"
    assert message.message_id == "<msg-001@acme.example>"
    assert message.in_reply_to == "<apply-001@headstart.local>"
    assert "availability next week" in message.body_text
    assert message.received_at is not None
