"""Heuristic reply drafter — offline default."""

from __future__ import annotations

import re

from app.reply_drafters.base import ReplyDrafter, register_reply_drafter
from app.reply_drafters.types import ReplyDraftContext, ReplyDraftResult

_SALARY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"salary", re.I),
    re.compile(r"compensation", re.I),
    re.compile(r"pay\s+range", re.I),
)

_WORK_AUTH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"work\s+authorization", re.I),
    re.compile(r"visa\s+sponsor", re.I),
    re.compile(r"eligible\s+to\s+work", re.I),
    re.compile(r"right\s+to\s+work", re.I),
)

_AVAILABILITY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"availability", re.I),
    re.compile(r"when\s+can\s+you\s+start", re.I),
    re.compile(r"notice\s+period", re.I),
    re.compile(r"start\s+date", re.I),
)


@register_reply_drafter("heuristic")
class HeuristicReplyDrafter(ReplyDrafter):
    """Draft recruiter replies from profile fields without external calls."""

    def __init__(self, *, settings: object | None = None) -> None:
        pass

    def draft(self, ctx: ReplyDraftContext) -> ReplyDraftResult:
        return _build_reply(ctx)


def _build_reply(ctx: ReplyDraftContext) -> ReplyDraftResult:
    haystack = f"{ctx.inbound_subject}\n{ctx.inbound_body}"
    profile = ctx.profile
    company = ""
    if ctx.linked_application is not None and ctx.linked_application.company.strip():
        company = ctx.linked_application.company.strip()
    elif ctx.inbound_from and "@" in ctx.inbound_from:
        company = ctx.inbound_from.rsplit("@", 1)[0]

    greeting = f"Hi{(' ' + company) if company else ''},"
    paragraphs = [greeting, "Thank you for your message."]

    if _matches_any(_SALARY_PATTERNS, haystack):
        salary = _profile_answer(profile.answers, ("salary", "salary_expectations", "compensation"))
        if salary:
            paragraphs.append(f"My salary expectations are {salary.rstrip('.')}.")
        else:
            paragraphs.append(
                "I'm open to discussing compensation once I learn more about the role and scope."
            )
    elif _matches_any(_WORK_AUTH_PATTERNS, haystack):
        work_auth = _profile_answer(
            profile.answers, ("work_authorization", "work_auth", "visa_status")
        )
        if work_auth:
            paragraphs.append(f"Regarding work authorization: {work_auth.rstrip('.')}.")
        else:
            paragraphs.append(
                "I'm happy to discuss work authorization details — please let me know "
                "what information you need."
            )
    elif _matches_any(_AVAILABILITY_PATTERNS, haystack):
        availability = _profile_answer(
            profile.answers, ("availability", "notice_period", "start_date")
        )
        if availability:
            paragraphs.append(f"Regarding timing: {availability.rstrip('.')}.")
        else:
            paragraphs.append(
                "I'm flexible on start date and can share availability for next steps."
            )
    else:
        job_title = ""
        if ctx.linked_application is not None:
            job_title = ctx.linked_application.job_title.strip()
        role_phrase = f" for the {job_title} role" if job_title else ""
        paragraphs.append(
            f"I remain very interested in this opportunity{role_phrase} and would "
            "welcome the chance to continue the conversation."
        )

    paragraphs.append("Best regards,")
    signature = profile.full_name.strip() or profile.email.strip() or "Candidate"
    paragraphs.append(signature)

    subject = _reply_subject(ctx.inbound_subject)
    return ReplyDraftResult(
        subject=subject,
        body="\n\n".join(paragraphs),
        notes="Heuristic template reply from profile fields.",
    )


def _reply_subject(original: str) -> str:
    subject = original.strip()
    if not subject:
        return "Re: Your message"
    if subject.lower().startswith("re:"):
        return subject
    return f"Re: {subject}"


def _profile_answer(answers: dict[str, str], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = answers.get(key, "")
        if str(value).strip():
            return str(value).strip()
    return ""


def _matches_any(patterns: tuple[re.Pattern[str], ...], text: str) -> bool:
    return any(pattern.search(text) for pattern in patterns)
