"""Reply-drafter prompt builder and JSON parsing coverage."""

import json

import pytest

from app.email_classifiers.types import LinkedApplicationContext
from app.reply_drafters.prompts import SYSTEM_PROMPT, parse_reply_json, user_prompt
from app.reply_drafters.types import ReplyDraftContext
from app.schemas.profile import ProfileData


def test_system_prompt_is_exposed() -> None:
    assert "JSON" in SYSTEM_PROMPT


def test_user_prompt_includes_every_populated_field() -> None:
    ctx = ReplyDraftContext(
        inbound_from="recruiter@acme.com",
        inbound_subject="Follow up",
        inbound_body="Are you still interested?",
        classification_label="follow_up",
        linked_application=LinkedApplicationContext(
            seen_job_id=42, job_title="Engineer", company="ACME"
        ),
        profile=ProfileData(
            full_name="Ada",
            email="ada@example.com",
            phone="+1 555",
            location="Berlin",
            answers={"salary": "150k", "empty_answer": "   "},
            skills=["Python", "SQL"],
        ),
    )
    prompt = user_prompt(ctx)
    assert "- From: recruiter@acme.com" in prompt
    assert "- Subject: Follow up" in prompt
    assert "- Body: Are you still interested?" in prompt
    assert "- Classification: follow_up" in prompt
    assert "- Job ID: 42" in prompt
    assert "- Title: Engineer" in prompt
    assert "- Company: ACME" in prompt
    assert "- Name: Ada" in prompt
    assert "- Email: ada@example.com" in prompt
    assert "- Phone: +1 555" in prompt
    assert "- Location: Berlin" in prompt
    assert "- salary: 150k" in prompt
    assert "empty_answer" not in prompt
    assert "- Skills: Python, SQL" in prompt


def test_user_prompt_linked_application_without_title_or_company() -> None:
    ctx = ReplyDraftContext(
        inbound_body="Hi.",
        linked_application=LinkedApplicationContext(seen_job_id=7),
        profile=ProfileData(),
    )
    prompt = user_prompt(ctx)
    assert "- Job ID: 7" in prompt
    assert "- Title:" not in prompt
    assert "- Company:" not in prompt


def test_user_prompt_omits_empty_fields() -> None:
    prompt = user_prompt(ReplyDraftContext(profile=ProfileData()))
    assert "- From:" not in prompt
    assert "Linked application:" not in prompt
    assert "Draft a reply the candidate can review before sending." in prompt


def test_parse_reply_json_strips_code_fence() -> None:
    raw = "```json\n" + json.dumps({"subject": "Re: x", "body": "Hello", "notes": "n"}) + "\n```"
    result = parse_reply_json(raw)
    assert result.subject == "Re: x"
    assert result.body == "Hello"
    assert result.notes == "n"


def test_parse_reply_json_rejects_empty_body() -> None:
    with pytest.raises(ValueError, match="body is empty"):
        parse_reply_json(json.dumps({"subject": "Re: x", "body": ""}))


def test_parse_reply_json_rejects_non_object() -> None:
    with pytest.raises(ValueError, match="must be a JSON object"):
        parse_reply_json(json.dumps(["not", "an", "object"]))
