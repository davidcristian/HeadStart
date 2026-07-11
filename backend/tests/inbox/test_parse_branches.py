"""Branch coverage for RFC 822 parsing helpers (decode/body/date edge cases)."""

from email.message import EmailMessage, Message

from app.inbox.parse import decode_mime_header, extract_body_text, parse_rfc822


def test_decode_mime_header_empty_and_none() -> None:
    assert decode_mime_header(None) == ""
    assert decode_mime_header("") == ""


def test_decode_mime_header_falls_back_on_parse_error() -> None:
    bad = "=?utf-8?B?not-valid-base64!!?="
    assert decode_mime_header(bad) == bad


def test_decode_mime_header_decodes_encoded_word() -> None:
    assert decode_mime_header("=?utf-8?q?Hello_World?=") == "Hello World"


def test_extract_body_text_multipart_prefers_plain() -> None:
    msg = EmailMessage()
    msg["From"] = "a@example.com"
    msg["To"] = "b@example.com"
    msg["Subject"] = "Multipart"
    msg.set_content("plain body")
    msg.add_alternative("<p>html body</p>", subtype="html")
    parsed = parse_rfc822(uid=1, raw_bytes=msg.as_bytes())
    assert "plain body" in parsed.body_text


def test_extract_body_text_multipart_skips_attachment_and_returns_empty() -> None:
    container = EmailMessage()
    container["From"] = "a@example.com"
    container["Subject"] = "Attachment only"
    container.make_mixed()
    attachment = EmailMessage()
    attachment.set_content("attached bytes")
    attachment["Content-Disposition"] = "attachment"
    container.attach(attachment)
    assert extract_body_text(container) == ""


def test_extract_body_text_multipart_html_only_strips_tags() -> None:
    # HTML-only multipart/alternative (no text/plain) must still yield readable text.
    msg = EmailMessage()
    msg["From"] = "recruiter@acme.example"
    msg["To"] = "candidate@example.com"
    msg["Subject"] = "Interview"
    msg.make_alternative()
    html_part = EmailMessage()
    html_part.set_content(
        "<p>We&nbsp;have <b>availability</b> next week.</p>",
        subtype="html",
    )
    msg.attach(html_part)
    assert msg.is_multipart()
    parsed = parse_rfc822(uid=7, raw_bytes=msg.as_bytes())
    assert "availability" in parsed.body_text
    assert "next week" in parsed.body_text
    assert "<" not in parsed.body_text
    assert "We" in parsed.body_text


def test_extract_body_text_singlepart_html_strips_tags() -> None:
    raw = (
        b"Subject: Html only\r\nFrom: a@example.com\r\n"
        b"Content-Type: text/html; charset=utf-8\r\n\r\n"
        b"<div>Please reply &amp; confirm</div>\r\n"
    )
    parsed = parse_rfc822(uid=8, raw_bytes=raw)
    assert parsed.body_text == "Please reply & confirm"


def test_extract_body_text_multipart_html_non_bytes_skipped() -> None:
    # text/html part whose decode payload is None is skipped; later HTML wins.
    container = Message()
    container["Content-Type"] = "multipart/alternative; boundary=BOUND"
    empty_html = Message()
    empty_html["Content-Type"] = "text/html"
    empty_html.set_payload([Message()])  # multipart -> decode=True is None
    good_html = Message()
    good_html["Content-Type"] = "text/html"
    good_html.set_payload("<p>fallback body</p>")
    container.set_payload([empty_html, good_html])
    assert extract_body_text(container) == "fallback body"


def test_extract_body_text_multipart_plain_non_bytes_skipped() -> None:
    # The outer text/plain part is itself multipart, so get_payload(decode=True)
    # is None and the `isinstance(payload, bytes)` check fails -> `continue` back to
    # the loop (branch 32->27). walk() then yields the inner text/plain child whose
    # bytes payload is what ultimately gets returned.
    container = Message()
    container["Content-Type"] = "multipart/mixed; boundary=BOUND"
    plain_part = Message()
    plain_part["Content-Type"] = "text/plain"
    inner = Message()
    inner["Content-Type"] = "text/plain"
    inner.set_payload("nested")
    plain_part.set_payload([inner])  # makes the part multipart -> decode=True is None
    container.set_payload([plain_part])
    assert container.is_multipart() is True
    assert extract_body_text(container) == "nested"


def test_extract_body_text_singlepart_bytes_payload() -> None:
    raw = b"Subject: Plain\r\nFrom: a@example.com\r\n\r\nhello body\r\n"
    parsed = parse_rfc822(uid=2, raw_bytes=raw)
    assert "hello body" in parsed.body_text


def test_extract_body_text_singlepart_str_payload() -> None:
    # A non-multipart message whose get_payload(decode=True) yields a str hits the
    # isinstance(payload, str) branch (line 41 in parse.extract_body_text).
    class _StrPayloadMessage(Message):
        def is_multipart(self):  # type: ignore[override]
            return False

        def get_payload(self, i=None, decode=False):  # type: ignore[override]
            return "string payload" if decode else "string payload"

    assert extract_body_text(_StrPayloadMessage()) == "string payload"


def test_extract_body_text_singlepart_none_payload_returns_empty() -> None:
    class _NonePayloadMessage(Message):
        def is_multipart(self):  # type: ignore[override]
            return False

        def get_payload(self, i=None, decode=False):  # type: ignore[override]
            return None

    assert extract_body_text(_NonePayloadMessage()) == ""


def test_parse_rfc822_handles_bad_date_header() -> None:
    raw = b"Subject: T\r\nFrom: a@example.com\r\nDate: not-a-real-date\r\n\r\nbody\r\n"
    parsed = parse_rfc822(uid=3, raw_bytes=raw)
    assert parsed.received_at is None
