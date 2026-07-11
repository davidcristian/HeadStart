"""Generate tailored cover letters for auto-apply."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.ai.runtime_settings import resolve_ai_settings
from app.core.config import settings as default_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.cover_letters import CoverLetterContext, CoverLetterGenerator, get_cover_letter_generator
from app.email_classifiers.sanitize import looks_like_prompt_injection
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.profile import ProfileData
from app.services.jobs import JobService
from app.services.plan_limits import PlanLimitsService
from app.services.profiles import ProfileService

logger = get_logger(__name__)

LLM_PROVIDERS = frozenset({"openai", "gemini", "anthropic", "llamacpp"})
GeneratorFactory = Callable[[str, Any], CoverLetterGenerator]


class CoverLetterService:
    def __init__(
        self,
        session: Session,
        *,
        generator_factory: GeneratorFactory | None = None,
        settings: Any = default_settings,
    ) -> None:
        self.session = session
        self.users = UserRepository(session)
        self._factory = generator_factory or (
            lambda key, runtime: get_cover_letter_generator(key, settings=runtime)
        )
        self._settings = settings

    def generate(self, user_id: int, job_id: int) -> dict[str, str | bool]:
        """Draft a cover letter for one job; falls back to heuristic on LLM failure."""
        if not bool(getattr(self._settings, "cover_letters_enabled", True)):
            raise ValidationError("Cover letter generation is disabled")

        user = self.users.get(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found")

        job = JobService(self.session).get(job_id, user_id)
        profile = ProfileService(self.session).get_for_apply(user_id)
        if not profile.exists:
            raise ValidationError("Save an application profile before generating a cover letter")

        ctx = CoverLetterContext(
            job_title=job.title,
            company=job.company,
            location=job.location,
            salary=job.salary,
            job_url=job.url,
            job_summary=job.summary,
            profile=ProfileData.model_validate(profile.model_dump()),
        )

        requested = self._resolve_provider(user)
        injection = requested != "heuristic" and self._scraped_fields_look_injected(ctx)
        if injection:
            logger.warning(
                "cover letter for job %s: scraped posting fields matched injection "
                "patterns; forcing heuristic generator",
                job_id,
            )
            requested = "heuristic"

        if requested != "heuristic":
            try:
                text = self._generate_with(requested, user, ctx)
                return {
                    "cover_letter": self._truncate(text),
                    "provider": requested,
                    "fallback": False,
                    "injection_guarded": False,
                }
            except Exception as exc:
                logger.warning("cover letter provider %s failed: %s", requested, exc)

        text = self._generate_with("heuristic", user, ctx)
        return {
            "cover_letter": self._truncate(text),
            "provider": "heuristic",
            "fallback": (not injection) and requested != "heuristic",
            "injection_guarded": injection,
        }

    def _scraped_fields_look_injected(self, ctx: CoverLetterContext) -> bool:
        """True when untrusted posting/resume text matches instruction-injection patterns."""
        parts = (
            ctx.job_title,
            ctx.company,
            ctx.location,
            ctx.salary,
            ctx.job_summary,
            ctx.profile.resume_text,
        )
        return any(looks_like_prompt_injection(part) for part in parts if part)

    def _resolve_provider(self, user: User) -> str:
        if not PlanLimitsService(self.session).allows_summaries(user.id):
            return "heuristic"
        runtime = resolve_ai_settings(self._settings, user, "cover_letter")
        provider = str(runtime.summary_provider)
        if provider in LLM_PROVIDERS:
            return provider
        return "heuristic"

    def _generate_with(self, provider: str, user: User, ctx: CoverLetterContext) -> str:
        runtime = resolve_ai_settings(self._settings, user, "cover_letter")
        generator = self._factory(provider, runtime)
        text = generator.generate(ctx).strip()
        if not text:
            raise ValueError(f"cover letter provider {provider} returned empty text")
        return text

    def _truncate(self, text: str) -> str:
        max_chars = int(getattr(self._settings, "cover_letter_max_chars", 4000))
        if max_chars <= 0 or len(text) <= max_chars:
            return text
        return text[: max(0, max_chars - 1)].rstrip() + "\u2026"
