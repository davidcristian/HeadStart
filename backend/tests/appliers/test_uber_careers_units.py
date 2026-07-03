"""Unit-level branch coverage for the Uber Careers apply helper modules."""

import httpx
import pytest

from app.appliers.adapters.uber_careers_common import (
    is_uber_host,
    resolve_job_id,
    yes_no_answer,
)
from app.appliers.adapters.uber_careers_graphql import submit_application
from app.appliers.adapters.uber_careers_payload import (
    build_application_form_request,
    build_application_payload,
    build_phone_number,
)
from app.appliers.adapters.uber_careers_questions import (
    build_question_responses,
    fetch_additional_questions,
    missing_required_answers,
    normalize_question,
)
from app.schemas.profile import ProfileData, ProfileLinks
from tests.conftest import make_http_client


def _profile(**overrides: object) -> ProfileData:
    base: dict[str, object] = {
        "full_name": "Ada Lovelace",
        "email": "ada@example.com",
        "phone": "+1 555 0100",
        "links": ProfileLinks(),
        "answers": {},
    }
    base.update(overrides)
    return ProfileData(**base)


# --- uber_careers_common -------------------------------------------------


def test_resolve_job_id_skips_empty_candidate_and_matches_form_url() -> None:
    # job_external_id empty (skip), job_url matches the apply/form regex (line 61).
    url = "https://www.uber.com/us/en/careers/apply/form/154672"
    assert resolve_job_id({}, url, "") == 154672


def test_yes_no_answer_passthrough_for_freeform_value() -> None:
    assert yes_no_answer({"role": "Maybe later"}, "role") == "Maybe later"


def test_yes_no_answer_falls_back_to_default_when_blank() -> None:
    assert yes_no_answer({"role": "   "}, "role", default="No") == "No"


def test_is_uber_host_detects_uber_and_rejects_others() -> None:
    assert is_uber_host("https://www.uber.com/us/en/careers/list/1")
    assert is_uber_host("https://uber.com/careers")
    assert not is_uber_host("https://example.com/jobs/1")


# --- uber_careers_graphql ------------------------------------------------


def _graphql_client(payload: object) -> object:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return make_http_client(handler)


def _submit(payload: object) -> object:
    return submit_application(
        _graphql_client(payload),  # type: ignore[arg-type]
        application_form_request={"jobID": 1},
        referer="https://www.uber.com/us/en/careers/apply/form/1",
    )


def test_graphql_rejects_non_dict_body() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["not", "a", "dict"])

    with pytest.raises(ValueError, match="unexpected payload"):
        submit_application(
            make_http_client(handler),
            application_form_request={},
            referer="https://www.uber.com/us/en/careers/apply/form/1",
        )


def test_graphql_surfaces_error_list() -> None:
    with pytest.raises(ValueError, match="denied"):
        _submit({"errors": [{"message": "denied"}]})


def test_graphql_rejects_missing_data() -> None:
    with pytest.raises(ValueError, match="returned no data"):
        _submit({"data": "nope"})


def test_graphql_rejects_missing_submit_application_field() -> None:
    with pytest.raises(ValueError, match="missing submitApplication"):
        _submit({"data": {"other": 1}})


def test_graphql_first_error_message_unwraps_nested_json() -> None:
    with pytest.raises(ValueError, match="nested detail"):
        _submit({"errors": [{"message": '{"message": "nested detail"}'}]})


def test_graphql_first_error_message_keeps_invalid_json() -> None:
    with pytest.raises(ValueError, match="{not json"):
        _submit({"errors": [{"message": "{not json"}]})


def test_graphql_first_error_message_json_without_message() -> None:
    with pytest.raises(ValueError, match=r"\{\"code\": 5\}"):
        _submit({"errors": [{"message": '{"code": 5}'}]})


def test_graphql_first_error_message_skips_non_dict_and_blank() -> None:
    # First item is not a dict, second has a blank message, third has no message
    # key -> falls through to the "unknown GraphQL error" sentinel.
    with pytest.raises(ValueError, match="unknown GraphQL error"):
        _submit({"errors": ["oops", {"message": "   "}, {"other": 1}]})


# --- uber_careers_payload ------------------------------------------------


def test_build_form_request_requires_first_name() -> None:
    with pytest.raises(ValueError, match="full_name is required"):
        build_application_form_request(
            _profile(full_name="   "),
            job_id=1,
            job_title="Engineer",
            session_token=None,
            additional_questions=[],
            resume_file=None,
            include_resume_bytes=False,
        )


def test_build_form_request_requires_email() -> None:
    with pytest.raises(ValueError, match="email is required"):
        build_application_form_request(
            _profile(email="   "),
            job_id=1,
            job_title="Engineer",
            session_token=None,
            additional_questions=[],
            resume_file=None,
            include_resume_bytes=False,
        )


def test_build_form_request_includes_optional_agreements() -> None:
    profile = _profile(
        answers={
            "arbitration_agreement": "yes",
            "data_retention_question": "no",
        }
    )
    request = build_application_form_request(
        profile,
        job_id=1,
        job_title="Engineer",
        session_token="tok",
        additional_questions=[],
        resume_file=None,
        include_resume_bytes=False,
    )
    assert request["arbitrationAgreement"] is True
    assert request["dataRetentionQuestion"] is False


def test_build_application_payload_includes_cover_letter_preview() -> None:
    payload = build_application_payload(
        _profile(),
        job_id=1,
        job_title="Engineer",
        company="Uber",
        session_token=None,
        additional_questions=[],
        resume_file=None,
        cover_letter="  Dear Uber, hello.  ",
    )
    assert payload["cover_letter_preview"] == "Dear Uber, hello."


def test_build_application_payload_omits_blank_cover_letter() -> None:
    payload = build_application_payload(
        _profile(),
        job_id=1,
        job_title="Engineer",
        company="Uber",
        session_token=None,
        additional_questions=[],
        resume_file=None,
        cover_letter="   ",
    )
    assert "cover_letter_preview" not in payload


def test_build_phone_number_uses_explicit_answer_fields() -> None:
    # phone_number + phone_country_code present: number is non-empty (138->140),
    # does not start with "+" (140->152), country_code already set (142->152).
    profile = _profile(
        phone="",
        answers={"phone_number": "555 0100", "phone_country_code": "44"},
    )
    assert build_phone_number(profile) == {"countryCode": "44", "number": "5550100"}


def test_build_phone_number_us_eleven_digit_e164() -> None:
    profile = _profile(phone="+1 (415) 555-0100", answers={})
    assert build_phone_number(profile) == {"countryCode": "1", "number": "4155550100"}


def test_build_phone_number_long_intl_e164_splits_country_code() -> None:
    profile = _profile(phone="+44 7911 123456", answers={})
    assert build_phone_number(profile) == {"countryCode": "44", "number": "7911123456"}


def test_build_phone_number_short_e164_falls_back_to_us() -> None:
    # digits do not start with "1" and length <= 10 -> else branch (150-151),
    # then country_code stays set from that branch (skips 153).
    profile = _profile(phone="+20 100", answers={})
    assert build_phone_number(profile) == {"countryCode": "1", "number": "20100"}


def test_build_phone_number_defaults_country_code_when_missing() -> None:
    # Non-"+" number and no country code -> line 153 sets the "1" default.
    profile = _profile(phone="5550100", answers={})
    assert build_phone_number(profile) == {"countryCode": "1", "number": "5550100"}


def test_build_phone_number_e164_with_explicit_country_code() -> None:
    # "+"-prefixed number but country_code already set -> skips the digit-parsing
    # block (142->152) and keeps the provided code.
    profile = _profile(phone="+1 555 0100", answers={"phone_country_code": "1"})
    assert build_phone_number(profile) == {"countryCode": "1", "number": "15550100"}


# --- uber_careers_questions ----------------------------------------------


def _questions_client(payload: object) -> object:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return make_http_client(handler)


def _fetch(payload: object) -> object:
    return fetch_additional_questions(
        _questions_client(payload),  # type: ignore[arg-type]
        job_id=1,
        locale="en",
        locale_path="us/en",
    )


def test_fetch_questions_rejects_non_dict_payload() -> None:
    with pytest.raises(ValueError, match="unexpected payload"):
        _fetch(["nope"])


def test_fetch_questions_reports_dict_error_message() -> None:
    with pytest.raises(ValueError, match="down for maintenance"):
        _fetch({"status": "error", "data": {"message": "down for maintenance"}})


def test_fetch_questions_reports_raw_payload_when_no_message() -> None:
    with pytest.raises(ValueError, match="questions API failed"):
        _fetch({"status": "error", "data": "opaque"})


def test_fetch_questions_returns_empty_when_data_not_dict() -> None:
    assert _fetch({"status": "success", "data": "nope"}) == []


def test_fetch_questions_returns_empty_when_questions_not_list() -> None:
    assert _fetch({"status": "success", "data": {"additionalQuestions": "nope"}}) == []


def test_fetch_questions_drops_non_dict_rows() -> None:
    payload = {
        "status": "success",
        "data": {"additionalQuestions": [{"questionID": "Q1"}, "junk"]},
    }
    assert _fetch(payload) == [{"questionID": "Q1"}]


def test_normalize_question_prefers_flat_question_id() -> None:
    assert normalize_question({"questionID": " Q7 "})["question_id"] == "Q7"


def test_normalize_question_empty_when_no_id() -> None:
    assert normalize_question({"question": "hi"})["question_id"] == ""


def test_normalize_question_empty_when_nested_value_blank() -> None:
    # Nested questionId dict present but its value is falsy -> falls to "" (112->114).
    assert normalize_question({"questionId": {"value": ""}})["question_id"] == ""


def test_normalize_question_uses_field_name_fallback() -> None:
    normalized = normalize_question({"questionID": "Q7", "fieldName": " screening "})
    assert normalized["form_question_id"] == "screening"


def test_normalize_question_form_id_defaults_to_question_id() -> None:
    normalized = normalize_question({"questionID": "Q7"})
    assert normalized["form_question_id"] == "Q7"


def test_is_required_string_flag() -> None:
    assert normalize_question({"questionID": "Q7", "required": "true"})["required"] is True


def test_is_required_bool_false_continues_scan() -> None:
    # required=False (bool, not True) must not short-circuit; isRequired=True wins.
    normalized = normalize_question({"questionID": "Q7", "required": False, "isRequired": True})
    assert normalized["required"] is True


def test_build_question_responses_skips_unidentified_and_unanswered() -> None:
    questions = [
        {"question": "no id here"},
        {"questionID": "Q7", "formQuestionId": "fq7"},
    ]
    # No answer for Q7 either -> both skipped.
    assert build_question_responses(questions, {}) == []


def test_build_question_responses_matches_option_case_insensitively() -> None:
    question = {
        "questionID": "Q7",
        "formQuestionId": "fq7",
        "options": ["Yes, I do", "No"],
    }
    responses = build_question_responses([question], {"fq7": "yes, i do"})
    assert responses == [{"questionID": "Q7", "answer": "Yes, I do"}]


def test_build_question_responses_free_text_without_options() -> None:
    # No options list -> _match_option returns the raw answer (line 159).
    question = {"questionID": "Q7", "formQuestionId": "fq7"}
    responses = build_question_responses([question], {"fq7": "free text"})
    assert responses == [{"questionID": "Q7", "answer": "free text"}]


def test_build_question_responses_keeps_answer_without_matching_option() -> None:
    question = {
        "questionID": "Q7",
        "formQuestionId": "fq7",
        "options": ["A", "B"],
    }
    responses = build_question_responses([question], {"fq7": "C"})
    assert responses == [{"questionID": "Q7", "answer": "C"}]


def test_missing_required_skips_unidentified_required_question() -> None:
    # required but no resolvable id/form-key -> skipped, not reported missing.
    questions = [{"question": "no id", "required": True}]
    assert missing_required_answers(questions, {}) == []
