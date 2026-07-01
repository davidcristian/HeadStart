"""Profile section submission steps for live Workday applications."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.appliers.adapters.workday_common import WorkdayTarget
from app.appliers.adapters.workday_experience import (
    SectionSubmitResult,
    submit_educations,
    submit_work_experiences,
)
from app.appliers.adapters.workday_questionnaire import submit_questionnaires
from app.appliers.adapters.workday_skills import submit_languages, submit_skills
from app.appliers.adapters.workday_submit_payload import LiveSubmitProgress
from app.appliers.types import ApplyResult
from app.schemas.profile import ProfileData
from app.scrapers.http import HttpClient

SectionSubmitFn = Callable[..., list[SectionSubmitResult]]


def _first_failed(results: list[SectionSubmitResult]) -> SectionSubmitResult | None:
    return next((result for result in results if not result.ok), None)


def _run_section(
    progress: LiveSubmitProgress,
    submit_fn: SectionSubmitFn,
    *,
    error_message: str,
    application_id: str,
    http: HttpClient,
    target: WorkdayTarget,
    profile: ProfileData,
    job_path: str,
    config: dict[str, Any],
    csrf_token: str,
    session_id: str,
    credentials: dict[str, dict[str, str]] | None,
) -> tuple[list[SectionSubmitResult], ApplyResult | None]:
    """Run one profile section submitter and map failures to ApplyResult."""
    results = submit_fn(
        http,
        target=target,
        application_id=application_id,
        profile=profile,
        job_path=job_path,
        config=config,
        csrf_token=csrf_token,
        session_id=session_id,
        credentials=credentials,
    )
    failed = _first_failed(results)
    if failed is not None:
        return results, progress.failure(failed.error or error_message, application_id)
    return results, None


def submit_profile_sections(
    http: HttpClient,
    *,
    target: WorkdayTarget,
    application_id: str,
    profile: ProfileData,
    job_path: str,
    config: dict[str, Any],
    csrf_token: str,
    session_id: str,
    credentials: dict[str, dict[str, str]] | None,
    progress: LiveSubmitProgress,
) -> ApplyResult | None:
    """Submit profile sections and return a failure result if any step fails."""
    section_steps: list[tuple[SectionSubmitFn, str, str]] = [
        (submit_work_experiences, "experience_results", "workday work experience submit failed"),
        (submit_educations, "education_results", "workday education submit failed"),
        (submit_skills, "skill_results", "workday skills submit failed"),
        (submit_languages, "language_results", "workday languages submit failed"),
    ]
    for submit_fn, attr, error_message in section_steps:
        results, failure = _run_section(
            progress,
            submit_fn,
            error_message=error_message,
            application_id=application_id,
            http=http,
            target=target,
            profile=profile,
            job_path=job_path,
            config=config,
            csrf_token=csrf_token,
            session_id=session_id,
            credentials=credentials,
        )
        setattr(progress, attr, results)
        if failure is not None:
            return failure

    return None


def submit_questionnaire_sections(
    http: HttpClient,
    *,
    target: WorkdayTarget,
    application_id: str,
    profile: ProfileData,
    job_path: str,
    config: dict[str, Any],
    csrf_token: str,
    session_id: str,
    credentials: dict[str, dict[str, str]] | None,
    progress: LiveSubmitProgress,
) -> ApplyResult | None:
    """Submit questionnaires; return failure if any questionnaire step fails."""
    progress.questionnaire_results = submit_questionnaires(
        http,
        target=target,
        application_id=application_id,
        config=config,
        profile=profile,
        job_path=job_path,
        csrf_token=csrf_token,
        session_id=session_id,
        credentials=credentials,
    )
    failed = next(
        (result for result in progress.questionnaire_results if not result.ok),
        None,
    )
    if failed is not None:
        return progress.failure(
            failed.error or "workday questionnaire submit failed",
            application_id,
        )
    return None
