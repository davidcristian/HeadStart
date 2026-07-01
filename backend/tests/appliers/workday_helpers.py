"""Shared fixtures for Workday applier tests."""

import httpx

from app.schemas.profile import ProfileData, ProfileLinks

JOB_URL = (
    "https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers/"
    "job/US-CA-Santa-Clara/Senior-Software-Engineer_JR1001"
)

WORKDAY_CONFIG = {
    "tenant": "acme",
    "site": "AcmeCareers",
    "region": "wd5",
}

WORKDAY_CREDENTIALS = {
    "cookies": {
        "CALYPSO_SESSION": "session-token",
        "CALYPSO_CSRF_TOKEN": "csrf-token",
    },
    "headers": {},
    "session": {},
}


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


def institutionvalues_empty_response(request: httpx.Request) -> httpx.Response | None:
    """Return an empty institution-values payload when tests do not model lookups."""
    if "/institutionvalues/" in request.url.path:
        return httpx.Response(200, json={"total": 0, "data": []})
    return None
