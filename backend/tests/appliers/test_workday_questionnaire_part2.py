"""Tests for Workday questionnaire skip and error handling."""

import httpx
import pytest

from app.appliers.adapters.workday_common import WorkdayTarget, resolve_target
from app.appliers.adapters.workday_questionnaire import (
    preview_questionnaires,
    submit_questionnaires,
)
from app.schemas.profile import ProfileData
from tests.conftest import load_json_fixture, make_http_client


def _unexpected(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected request: {request.method} {request.url}")


def _target() -> WorkdayTarget:
    resolved = resolve_target({"tenant": "acme", "site": "AcmeCareers", "region": "wd5"}, "")
    assert resolved is not None
    return resolved


def _profile() -> ProfileData:
    return ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        answers={
            "q-work-auth": "Yes",
            "q-notice": "2 weeks",
        },
    )


def test_preview_questionnaires_skipped_by_config() -> None:
    preview = preview_questionnaires(
        make_http_client(_unexpected),
        target=_target(),
        config={"skip_questionnaires": True},
        profile=_profile(),
        job_path="loc/job",
        credentials=None,
        csrf_token=None,
        session_id=None,
    )
    assert preview == {"jobPostingInfo": {}, "questionnaires": {}}


def test_submit_questionnaires_skipped_by_config() -> None:
    assert (
        submit_questionnaires(
            make_http_client(_unexpected),
            target=_target(),
            application_id="app-1",
            config={"skip_questionnaires": True},
            profile=_profile(),
            job_path="loc/job",
            csrf_token="csrf",
            session_id="sess",
            credentials=None,
        )
        == []
    )


def test_submit_questionnaires_skips_when_no_answers() -> None:
    posting = {"jobPostingInfo": {"questionnaireId": "quest-primary-001"}}
    questionnaire = {"questions": [{"id": "q-unknown", "type": {"descriptor": "Text"}}]}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/job/loc/job" in path:
            return httpx.Response(200, json=posting)
        if path.endswith("/questionnaire/quest-primary-001"):
            return httpx.Response(200, json=questionnaire)
        return _unexpected(request)

    results = submit_questionnaires(
        make_http_client(handler),
        target=_target(),
        application_id="app-1",
        config={"skip_secondary_questionnaire": True, "skip_supplementary_questionnaire": True},
        profile=ProfileData(answers={}),
        job_path="loc/job",
        csrf_token="csrf",
        session_id="sess",
        credentials=None,
    )
    assert results == []


def test_submit_questionnaires_records_http_error() -> None:
    posting = {"jobPostingInfo": {"questionnaireId": "quest-primary-001"}}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/job/loc/job" in path:
            return httpx.Response(200, json=posting)
        if path.endswith("/questionnaire/quest-primary-001"):
            return httpx.Response(500, text="boom")
        return _unexpected(request)

    results = submit_questionnaires(
        make_http_client(handler),
        target=_target(),
        application_id="app-1",
        config={"skip_secondary_questionnaire": True, "skip_supplementary_questionnaire": True},
        profile=_profile(),
        job_path="loc/job",
        csrf_token="csrf",
        session_id="sess",
        credentials=None,
    )
    assert len(results) == 1
    assert results[0].ok is False


def test_submit_questionnaires_post_error_code_raises() -> None:
    posting = {"jobPostingInfo": {"questionnaireId": "quest-primary-001"}}
    questionnaire = load_json_fixture("workday_questionnaire.json")

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/job/loc/job" in path:
            return httpx.Response(200, json=posting)
        if path.endswith("/questionnaire/quest-primary-001"):
            return httpx.Response(200, json=questionnaire)
        if "questionnaireresponse" in path:
            return httpx.Response(200, json={"errorCode": "X", "message": "rejected"})
        return _unexpected(request)

    with pytest.raises(ValueError, match="rejected"):
        submit_questionnaires(
            make_http_client(handler),
            target=_target(),
            application_id="app-1",
            config={
                "skip_secondary_questionnaire": True,
                "skip_supplementary_questionnaire": True,
            },
            profile=_profile(),
            job_path="loc/job",
            csrf_token="csrf",
            session_id="sess",
            credentials=None,
        )


def test_submit_questionnaires_post_non_dict_raises() -> None:
    posting = {"jobPostingInfo": {"questionnaireId": "quest-primary-001"}}
    questionnaire = load_json_fixture("workday_questionnaire.json")

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/job/loc/job" in path:
            return httpx.Response(200, json=posting)
        if path.endswith("/questionnaire/quest-primary-001"):
            return httpx.Response(200, json=questionnaire)
        if "questionnaireresponse" in path:
            return httpx.Response(200, json=["not", "a", "dict"])
        return _unexpected(request)

    with pytest.raises(ValueError, match="unexpected payload"):
        submit_questionnaires(
            make_http_client(handler),
            target=_target(),
            application_id="app-1",
            config={
                "skip_secondary_questionnaire": True,
                "skip_supplementary_questionnaire": True,
            },
            profile=_profile(),
            job_path="loc/job",
            csrf_token="csrf",
            session_id="sess",
            credentials=None,
        )
