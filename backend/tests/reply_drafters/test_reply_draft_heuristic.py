"""Unit tests for heuristic reply drafter."""

from app.reply_drafters.adapters.heuristic import HeuristicReplyDrafter
from app.reply_drafters.types import ReplyDraftContext
from app.schemas.profile import ProfileData


def test_heuristic_drafts_salary_reply_from_profile_answers() -> None:
    ctx = ReplyDraftContext(
        inbound_subject="Salary expectations",
        inbound_from="recruiter@acme.com",
        inbound_body="What are your salary expectations for this role?",
        classification_label="follow_up",
        profile=ProfileData(
            full_name="Alex Example",
            answers={"salary_expectations": "$150,000 base"},
        ),
    )
    result = HeuristicReplyDrafter().draft(ctx)
    assert "$150,000" in result.body
    assert "Alex Example" in result.body
    assert result.subject.startswith("Re:")


def test_heuristic_drafts_general_interest_when_no_question_match() -> None:
    ctx = ReplyDraftContext(
        inbound_subject="Thanks for applying",
        inbound_body="We received your application and will review it.",
        classification_label="general",
        linked_application=None,
        profile=ProfileData(full_name="Alex Example"),
    )
    result = HeuristicReplyDrafter().draft(ctx)
    assert "interested" in result.body.lower()
    assert "Alex Example" in result.body
