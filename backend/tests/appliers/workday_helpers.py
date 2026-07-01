"""Shared fixtures for Workday applier tests."""

import httpx

from app.schemas.profile import ProfileData, ProfileLinks

JOB_URL = (
    "https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers/"
    "job/US-CA-Santa-Clara/Senior-Software-Engineer_JR1001"
)


def profile() -> ProfileData:
    return ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1 555 0100",
        location="Santa Clara, CA",
        links=ProfileLinks(
            linkedin="https://linkedin.com/in/ada",
            github="https://github.com/ada",
            website="https://ada.example",
        ),
        resume_text="Experienced engineer.",
        cover_letter_template="Dear {company}, I am excited about {job_title}.",
        answers={"work_authorization": "yes"},
    )


def unexpected_request(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected network call: {request.method} {request.url}")
