"""Service tests for cover-letter generation."""

from unittest.mock import MagicMock, patch

from app.cover_letters import get_cover_letter_generator
from app.schemas.profile import ApplyProfile
from app.services.cover_letters import CoverLetterService


def test_generate_returns_heuristic_for_free_plan() -> None:
    session = MagicMock()
    service = CoverLetterService(session)
    user = MagicMock()
    user.id = 42
    user.plan = "free"
    service.users.get = MagicMock(return_value=user)

    job = MagicMock()
    job.title = "Senior Engineer"
    job.company = "ACME"
    job.location = "Remote"
    job.salary = ""
    job.url = "https://example.com/jobs/1"
    job.summary = ""

    profile = ApplyProfile(
        exists=True,
        full_name="Ada Lovelace",
        cover_letter_template="Dear {company} team, I am excited about {job_title}.",
    )

    with (
        patch("app.services.cover_letters.JobService") as mock_jobs,
        patch("app.services.cover_letters.ProfileService") as mock_profiles,
        patch.object(service, "_resolve_provider", return_value="heuristic"),
    ):
        mock_jobs.return_value.get.return_value = job
        mock_profiles.return_value.get_for_apply.return_value = profile
        result = service.generate(42, 1)

    assert result["provider"] == "heuristic"
    assert result["fallback"] is False
    assert "Dear ACME team" in result["cover_letter"]


def test_generate_falls_back_when_llm_fails() -> None:
    session = MagicMock()
    service = CoverLetterService(session)
    user = MagicMock()
    user.id = 42
    user.plan = "pro"
    service.users.get = MagicMock(return_value=user)

    job = MagicMock()
    job.title = "Senior Engineer"
    job.company = "ACME"
    job.location = "Remote"
    job.salary = ""
    job.url = "https://example.com/jobs/1"
    job.summary = ""

    profile = ApplyProfile(
        exists=True,
        full_name="Ada Lovelace",
        cover_letter_template="Dear {company} team, I am excited about {job_title}.",
    )

    class FailingGenerator:
        def generate(self, ctx: object) -> str:
            raise RuntimeError("network down")

    def factory(key: str, runtime: object) -> object:
        if key == "heuristic":
            return get_cover_letter_generator("heuristic")
        return FailingGenerator()

    with (
        patch("app.services.cover_letters.JobService") as mock_jobs,
        patch("app.services.cover_letters.ProfileService") as mock_profiles,
        patch.object(service, "_resolve_provider", return_value="openai"),
    ):
        mock_jobs.return_value.get.return_value = job
        mock_profiles.return_value.get_for_apply.return_value = profile
        service._factory = factory  # type: ignore[method-assign]
        result = service.generate(42, 1)

    assert result["provider"] == "heuristic"
    assert result["fallback"] is True
    assert "ACME" in result["cover_letter"]
