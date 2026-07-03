"""Unit tests for Google Careers resume upload internals (protobuf, headers, errors)."""

from __future__ import annotations

import base64

import httpx
import pytest

from app.appliers.adapters.google_careers_resume import (
    _MAX_RESUME_BYTES,
    GoogleCareersResumeAttachment,
    _decode_response_body,
    _extract_resume_attachment_fields,
    _first_length_delimited,
    _first_string,
    _read_varint,
    _skip_field,
    parse_upload_response,
    preview_resume_upload,
    sapisidhash_headers,
    upload_resume_attachment,
)
from app.schemas.profile import ResumeFile
from tests.conftest import make_http_client


def _resume(**overrides: object) -> ResumeFile:
    base: dict[str, object] = {
        "filename": "resume.pdf",
        "content_type": "application/pdf",
        "size_bytes": 4,
        "data": b"%PDF",
    }
    base.update(overrides)
    return ResumeFile(**base)


def _string_field(field_number: int, value: str) -> bytes:
    tag = (field_number << 3) | 2
    encoded = value.encode("utf-8")
    return bytes([tag]) + _varint(len(encoded)) + encoded


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            break
    return bytes(out)


def _attachment_response(attachment_id: str, filename: str) -> bytes:
    inner = _string_field(1, attachment_id) + _string_field(2, filename)
    return bytes([(1 << 3) | 2]) + _varint(len(inner)) + inner


# --- sapisidhash -------------------------------------------------------------


def test_sapisidhash_headers_without_token() -> None:
    assert sapisidhash_headers({}) == {}


def test_sapisidhash_headers_with_secure_1papisid() -> None:
    headers = sapisidhash_headers({"__Secure-1PAPISID": "tok"})
    assert headers["Authorization"].startswith("SAPISIDHASH ")


# --- upload_resume_attachment errors -----------------------------------------


def test_upload_resume_attachment_rejects_oversize() -> None:
    big = _resume(size_bytes=_MAX_RESUME_BYTES + 1)
    with pytest.raises(ValueError, match="2 MB limit"):
        upload_resume_attachment(make_http_client(_unexpected), big)


def test_upload_resume_attachment_missing_session_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # Start command returns no X-Goog-Upload-URL header.
        return httpx.Response(200, text="")

    with pytest.raises(ValueError, match="did not return X-Goog-Upload-URL"):
        upload_resume_attachment(make_http_client(handler), _resume())


def test_upload_resume_attachment_keeps_real_filename_when_generic() -> None:
    session_url = "https://upload.google.test/session"
    body = base64.b64encode(_attachment_response("a1", "resume")).decode("ascii")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == session_url:
            return httpx.Response(200, text=body)
        return httpx.Response(200, headers={"x-goog-upload-url": session_url}, text="")

    attachment = upload_resume_attachment(
        make_http_client(handler),
        _resume(filename="my-cv.pdf"),
    )
    # Response filename "resume" is generic -> replaced by real upload filename.
    assert attachment.filename == "my-cv.pdf"
    assert attachment.attachment_id == "a1"


def test_upload_resume_attachment_keeps_response_filename() -> None:
    session_url = "https://upload.google.test/session"
    body = base64.b64encode(_attachment_response("a1", "custom.pdf")).decode("ascii")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == session_url:
            return httpx.Response(200, text=body)
        return httpx.Response(200, headers={"X-Goog-Upload-URL": session_url}, text="")

    attachment = upload_resume_attachment(make_http_client(handler), _resume())
    assert attachment.filename == "custom.pdf"


# --- parse_upload_response ---------------------------------------------------


def test_parse_upload_response_missing_attachment_id_raises() -> None:
    # A protobuf message whose field 1 (attachment) is absent -> no attachment id.
    empty = base64.b64encode(_string_field(5, "irrelevant")).decode("ascii")
    with pytest.raises(ValueError, match="did not include an attachment id"):
        parse_upload_response(empty)


def test_parse_upload_response_defaults_filename() -> None:
    body = base64.b64encode(
        bytes([(1 << 3) | 2])
        + _varint(len(_string_field(1, "only-id")))
        + _string_field(1, "only-id")
    ).decode("ascii")
    attachment = parse_upload_response(body)
    assert attachment == GoogleCareersResumeAttachment(attachment_id="only-id", filename="resume")


# --- _decode_response_body ---------------------------------------------------


def test_decode_response_body_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty body"):
        _decode_response_body("   ")


def test_decode_response_body_valid_base64() -> None:
    assert _decode_response_body(base64.b64encode(b"abc").decode()) == b"abc"


def test_decode_response_body_non_base64_falls_back_to_utf8() -> None:
    # "@@@" is not valid base64 in validate mode -> returned as utf-8 bytes.
    assert _decode_response_body("@@@") == b"@@@"


# --- protobuf primitives -----------------------------------------------------


def test_extract_resume_attachment_fields_no_message() -> None:
    # Payload has no field-1 length-delimited message.
    assert _extract_resume_attachment_fields(_string_field(9, "x")) == ("", "")


def test_first_length_delimited_skips_other_fields() -> None:
    # A varint field (wire type 0) precedes the target field-1 message.
    payload = bytes([(3 << 3) | 0]) + _varint(42) + _string_field(1, "target")
    chunk = _first_length_delimited(payload, field_number=1)
    assert chunk is not None


def test_first_length_delimited_missing_returns_none() -> None:
    assert _first_length_delimited(_string_field(2, "x"), field_number=1) is None


def test_first_string_none_when_missing() -> None:
    assert _first_string(_string_field(2, "x"), field_number=1) is None


def test_first_string_invalid_utf8_returns_none() -> None:
    tag = (1 << 3) | 2
    invalid = bytes([tag]) + _varint(1) + b"\xff"
    assert _first_string(invalid, field_number=1) is None


def test_read_varint_multibyte() -> None:
    value, index = _read_varint(_varint(300), 0)
    assert value == 300
    assert index == 2


def test_read_varint_truncated_raises() -> None:
    with pytest.raises(ValueError, match="truncated varint"):
        _read_varint(b"\x80", 0)


def test_read_varint_overlong_raises() -> None:
    # 10 continuation bytes push shift past 63 -> break then raises.
    with pytest.raises(ValueError, match="truncated varint"):
        _read_varint(b"\x80" * 10, 0)


def test_preview_resume_upload_none() -> None:
    assert preview_resume_upload(None) is None


def test_skip_field_wire_types() -> None:
    # wire type 0 (varint)
    assert _skip_field(_varint(5), 0, 0) == 1
    # wire type 1 (64-bit)
    assert _skip_field(b"\x00" * 8, 0, 1) == 8
    # wire type 2 (length-delimited)
    data = _varint(3) + b"abc"
    assert _skip_field(data, 0, 2) == len(data)
    # wire type 5 (32-bit)
    assert _skip_field(b"\x00" * 4, 0, 5) == 4


def test_skip_field_unsupported_wire_type_raises() -> None:
    with pytest.raises(ValueError, match="unsupported wire type"):
        _skip_field(b"", 0, 3)


def _unexpected(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected network call: {request.method} {request.url}")
