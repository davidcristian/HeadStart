"""Shared LLM prompts for recruiter reply drafting."""

from __future__ import annotations

import json
import re

from app.reply_drafters.types import ReplyDraftContext, ReplyDraftResult

SYSTEM_PROMPT = (
    "You draft concise, professional email replies for a job candidate responding "
    "to recruiter follow-up messages. Use only facts from the candidate profile. "
    "Write plain text suitable for email (no markdown). Keep replies under 200 words. "
    "Answer the recruiter's questions directly. Do not invent employers, salaries, "
    "or work authorization status that are not in the profile. "
    "Respond with a single JSON object (no markdown fences) with keys: "
    '"subject", "body", "notes". '
    '"subject" is the reply subject line (usually Re: original). '
    '"body" is the email body. '
    '"notes" is one short sentence explaining assumptions, or empty string.'
)


def user_prompt(ctx: ReplyDraftContext) -> str:
    """Build the user message for LLM reply drafting."""
    profile = ctx.profile
    lines = ["Inbound recruiter email:"]
    if ctx.inbound_from:
        lines.append(f"- From: {ctx.inbound_from}")
    if ctx.inbound_subject:
        lines.append(f"- Subject: {ctx.inbound_subject}")
    if ctx.inbound_body:
        lines.append(f"- Body: {ctx.inbound_body}")
    if ctx.classification_label:
        lines.append(f"- Classification: {ctx.classification_label}")
    if ctx.linked_application is not None:
        app = ctx.linked_application
        lines.append("")
        lines.append("Linked application:")
        lines.append(f"- Job ID: {app.seen_job_id}")
        if app.job_title:
            lines.append(f"- Title: {app.job_title}")
        if app.company:
            lines.append(f"- Company: {app.company}")
    lines.append("")
    lines.append("Candidate profile:")
    if profile.full_name:
        lines.append(f"- Name: {profile.full_name}")
    if profile.email:
        lines.append(f"- Email: {profile.email}")
    if profile.phone:
        lines.append(f"- Phone: {profile.phone}")
    if profile.location:
        lines.append(f"- Location: {profile.location}")
    if profile.answers:
        for key, value in sorted(profile.answers.items()):
            if str(value).strip():
                lines.append(f"- {key}: {value}")
    if profile.skills:
        lines.append(f"- Skills: {', '.join(profile.skills[:10])}")
    lines.append("")
    lines.append("Draft a reply the candidate can review before sending.")
    return "\n".join(lines)


def parse_reply_json(raw: str) -> ReplyDraftResult:
    """Parse LLM JSON into a validated reply draft."""
    payload = _load_json_object(raw)
    subject = str(payload.get("subject", "") or "").strip()
    body = str(payload.get("body", "") or "").strip()
    notes = str(payload.get("notes", "") or "").strip()
    if not body:
        raise ValueError("reply draft body is empty")
    return ReplyDraftResult(subject=subject, body=body, notes=notes)


def _load_json_object(raw: str) -> dict[str, object]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("reply draft response must be a JSON object")
    return parsed
