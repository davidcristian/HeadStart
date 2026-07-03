"""Email-classifier prompt builder and JSON parsing coverage."""

import json
from datetime import UTC, datetime

import pytest

from app.email_classifiers.prompts import (
    SYSTEM_PROMPT,
    parse_classification_json,
    user_prompt,
)
from app.email_classifiers.types import EmailClassifyContext, LinkedApplicationContext
from app.inbox.types import InboxMessage


def test_system_prompt_is_exposed() -> None:
    assert "out_of_scope" in SYSTEM_PROMPT


def test_user_prompt_includes_every_populated_field() -> None:
    ctx = EmailClassifyContext(
        message=InboxMessage(
            uid=1,
            from_addr="recruiter@acme.com",
            to_addrs=["me@example.com", "cc@example.com"],
            subject="Interview?",
            body_text="Are you available next week?",
            received_at=datetime(2026, 6, 1, 9, 0, tzinfo=UTC),
        ),
        linked_application=LinkedApplicationContext(
            seen_job_id=99,
            job_title="Engineer",
            company="ACME",
            employer_domain="acme.com",
        ),
    )
    prompt = user_prompt(ctx)
    assert "- From: recruiter@acme.com" in prompt
    assert "- To: me@example.com, cc@example.com" in prompt
    assert "- Subject: Interview?" in prompt
    assert "- Received: 2026-06-01T09:00:00+00:00" in prompt
    assert "- Body: Are you available next week?" in prompt
    assert "- Job ID: 99" in prompt
    assert "- Title: Engineer" in prompt
    assert "- Company: ACME" in prompt
    assert "- Employer domain: acme.com" in prompt


def test_user_prompt_linked_application_without_optional_fields() -> None:
    ctx = EmailClassifyContext(
        message=InboxMessage(uid=1),
        linked_application=LinkedApplicationContext(seen_job_id=7),
    )
    prompt = user_prompt(ctx)
    assert "- Job ID: 7" in prompt
    assert "- Title:" not in prompt
    assert "- Company:" not in prompt
    assert "- Employer domain:" not in prompt


def test_user_prompt_omits_empty_message_fields() -> None:
    prompt = user_prompt(EmailClassifyContext(message=InboxMessage(uid=1)))
    assert "- From:" not in prompt
    assert "- To:" not in prompt
    assert "- Received:" not in prompt
    assert "Linked application:" not in prompt
    assert "Return the JSON classification object." in prompt


def test_parse_classification_json_strips_fence_and_clamps_confidence() -> None:
    raw = "```json\n" + json.dumps({"label": "general", "confidence": 5, "reason": "r"}) + "\n```"
    result = parse_classification_json(raw)
    assert result.label == "general"
    assert result.confidence == 1.0
    assert result.reason == "r"


def test_parse_classification_json_accepts_string_confidence() -> None:
    result = parse_classification_json(json.dumps({"label": "rejection", "confidence": "0.4"}))
    assert result.confidence == 0.4


def test_parse_classification_json_rejects_unknown_label() -> None:
    with pytest.raises(ValueError, match="unknown classification label"):
        parse_classification_json(json.dumps({"label": "nope", "confidence": 0.5}))


def test_parse_classification_json_rejects_non_numeric_confidence() -> None:
    with pytest.raises(ValueError, match="confidence must be a number"):
        parse_classification_json(json.dumps({"label": "general", "confidence": [1, 2]}))


def test_parse_classification_json_rejects_non_object() -> None:
    with pytest.raises(ValueError, match="must be a JSON object"):
        parse_classification_json(json.dumps(["not", "an", "object"]))
