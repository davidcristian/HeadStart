"""Branch coverage for the heuristic reply drafter."""

from app.email_classifiers.types import LinkedApplicationContext
from app.reply_drafters.adapters.heuristic import HeuristicReplyDrafter
from app.reply_drafters.types import ReplyDraftContext
from app.schemas.profile import ProfileData


def _draft(ctx: ReplyDraftContext) -> str:
    return HeuristicReplyDrafter().draft(ctx).body


def test_company_from_linked_application_over_from_addr() -> None:
    ctx = ReplyDraftContext(
        inbound_subject="Re: role",
        inbound_from="recruiter@acme.com",
        inbound_body="Just checking in.",
        linked_application=LinkedApplicationContext(seen_job_id=1, company="Globex"),
        profile=ProfileData(full_name="Alex"),
    )
    assert HeuristicReplyDrafter().draft(ctx).body.startswith("Hi Globex,")


def test_company_from_from_addr_domain_when_no_application() -> None:
    ctx = ReplyDraftContext(
        inbound_from="jobs@acme.com",
        inbound_body="Hello there.",
        profile=ProfileData(full_name="Alex"),
    )
    assert HeuristicReplyDrafter().draft(ctx).body.startswith("Hi jobs,")


def test_salary_without_answer_uses_generic_line() -> None:
    ctx = ReplyDraftContext(
        inbound_body="What is your salary expectation?",
        profile=ProfileData(full_name="Alex"),
    )
    assert "open to discussing compensation" in _draft(ctx)


def test_work_auth_with_and_without_answer() -> None:
    body = "Do you have work authorization / need visa sponsorship?"
    with_answer = ReplyDraftContext(
        inbound_body=body,
        profile=ProfileData(full_name="Alex", answers={"work_authorization": "US citizen"}),
    )
    assert "Regarding work authorization: US citizen." in _draft(with_answer)

    without_answer = ReplyDraftContext(inbound_body=body, profile=ProfileData(full_name="Alex"))
    assert "happy to discuss work authorization" in _draft(without_answer)


def test_availability_with_and_without_answer() -> None:
    body = "What is your availability / notice period?"
    with_answer = ReplyDraftContext(
        inbound_body=body,
        profile=ProfileData(full_name="Alex", answers={"notice_period": "2 weeks"}),
    )
    assert "Regarding timing: 2 weeks." in _draft(with_answer)

    without_answer = ReplyDraftContext(inbound_body=body, profile=ProfileData(full_name="Alex"))
    assert "flexible on start date" in _draft(without_answer)


def test_general_interest_mentions_role_from_linked_application() -> None:
    ctx = ReplyDraftContext(
        inbound_body="Thanks for your interest.",
        linked_application=LinkedApplicationContext(seen_job_id=1, job_title="Engineer"),
        profile=ProfileData(full_name="Alex"),
    )
    assert "for the Engineer role" in _draft(ctx)


def test_signature_falls_back_to_email_then_candidate() -> None:
    email_only = ReplyDraftContext(
        inbound_body="Hi.", profile=ProfileData(email="alex@example.com")
    )
    assert _draft(email_only).endswith("alex@example.com")

    nothing = ReplyDraftContext(inbound_body="Hi.", profile=ProfileData())
    assert _draft(nothing).endswith("Candidate")


def test_reply_subject_variants() -> None:
    empty = ReplyDraftContext(inbound_subject="", inbound_body="Hi.", profile=ProfileData())
    assert HeuristicReplyDrafter().draft(empty).subject == "Re: Your message"

    already = ReplyDraftContext(
        inbound_subject="RE: hello", inbound_body="Hi.", profile=ProfileData()
    )
    assert HeuristicReplyDrafter().draft(already).subject == "RE: hello"
