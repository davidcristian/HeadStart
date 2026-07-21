"""Apply-adapter payload regressions (kept out of the per-adapter files for size)."""

from __future__ import annotations

from app.appliers.adapters.ashby import build_application_payload as ashby_payload
from app.appliers.adapters.meta_careers_detail import parse_job_detail_response
from app.appliers.adapters.meta_careers_payload import build_application_state
from app.schemas.profile import ApplyProfile, ProfileData, ResumeFile
from tests.conftest import load_json_fixture

META_JOB_ID = "2132019417725760"
META_DETAIL_FIXTURE = "meta_careers_job_details.json"


def test_meta_build_application_state_keeps_work_arrays_aligned() -> None:
    """Every work* column is built from one filtered list, so a row with a blank
    company/title can't desync employer/title/date pairing."""
    detail = parse_job_detail_response(
        load_json_fixture(META_DETAIL_FIXTURE), requisition_id=META_JOB_ID
    )
    profile = ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        work_experience=[
            {"company": "Alpha Inc", "job_title": "", "start_month": 1, "start_year": 2020},
            {
                "company": "",
                "job_title": "Staff Engineer",
                "start_month": 6,
                "start_year": 2021,
                "is_current": True,
            },
        ],
    )
    state = build_application_state(detail, profile, company="Meta", job_title=detail.title)

    columns = ["workEmployerNames", "workPositionNames", "workStartMonths", "workStartYears"]
    assert {len(state[column]) for column in columns} == {2}
    assert state["workEmployerNames"] == ["Alpha Inc", ""]
    assert state["workPositionNames"] == ["", "Staff Engineer"]
    # Index i still describes one job: Alpha Inc started 1/2020, the Staff role 6/2021.
    assert state["workStartMonths"] == ["1", "6"]
    assert state["workStartYears"] == ["2020", "2021"]
    assert state["workIsCurrent"] == [False, True]


def _ashby_profile_with_resume() -> ApplyProfile:
    resume = ResumeFile(
        filename="resume.pdf", content_type="application/pdf", size_bytes=4, data=b"%PDF"
    )
    return ApplyProfile(
        full_name="Ada Lovelace", email="ada@example.com", exists=True, resume_file=resume
    )


def test_ashby_multipart_carries_unpublished_job_posting_guard() -> None:
    """The allow-unpublished guard must survive the resume (multipart) path."""
    profile = _ashby_profile_with_resume()
    guarded = ashby_payload(
        "job-1",
        profile,
        job_title="Role",
        company="ACME",
        config={"allow_unpublished_job_posting": False},
    )
    assert guarded["payload"]["allowSubmissionForUnpublishedJobPosting"] is False
    assert guarded["multipart"]["data"]["allowSubmissionForUnpublishedJobPosting"] == "false"


def test_ashby_multipart_omits_guard_when_unpublished_allowed() -> None:
    profile = _ashby_profile_with_resume()
    ungated = ashby_payload("job-1", profile, job_title="Role", company="ACME", config={})
    assert "allowSubmissionForUnpublishedJobPosting" not in ungated["multipart"]["data"]
    assert "allowSubmissionForUnpublishedJobPosting" not in ungated["payload"]
