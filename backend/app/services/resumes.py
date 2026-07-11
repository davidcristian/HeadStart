"""Generate tailored resume PDFs from LaTeX templates."""

from __future__ import annotations

import base64
import hashlib
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.ai.runtime_settings import resolve_ai_settings
from app.core.config import settings as default_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.email_classifiers.sanitize import looks_like_prompt_injection
from app.models.user import User
from app.repositories.users import UserRepository
from app.resumes import ResumeCurationContext, ResumeCurator, get_resume_curator
from app.resumes.compile import compile_latex_to_pdf, compile_latex_workspace
from app.resumes.template import default_template_tex, render_resume_template
from app.resumes.template_bundle import render_template_bundle
from app.resumes.types import CuratedResumeFields
from app.schemas.profile import ProfileData
from app.services.application_artifacts import ApplicationArtifactService
from app.services.jobs import JobService
from app.services.plan_limits import PlanLimitsService
from app.services.profiles import ProfileService

logger = get_logger(__name__)

LLM_PROVIDERS = frozenset({"openai", "gemini", "anthropic", "llamacpp"})
CuratorFactory = Callable[[str, Any], ResumeCurator]
CompileFn = Callable[[str], bytes]
BundleCompileFn = Callable[[dict[str, bytes], str], bytes]


class ResumeService:
    def __init__(
        self,
        session: Session,
        *,
        curator_factory: CuratorFactory | None = None,
        compile_fn: CompileFn | None = None,
        bundle_compile_fn: BundleCompileFn | None = None,
        settings: Any = default_settings,
    ) -> None:
        self.session = session
        self.users = UserRepository(session)
        self._factory = curator_factory or (
            lambda key, runtime: get_resume_curator(key, settings=runtime)
        )
        self._compile = compile_fn or compile_latex_to_pdf
        # Keep the injected fn (or None for the default) so the identity check in
        # `_compile_bundle` is reliable; a bound-method default breaks `is`.
        self._bundle_compile = bundle_compile_fn
        self._settings = settings

    def generate(self, user_id: int, job_id: int) -> dict[str, str | int | bool]:
        """Curate placeholders, render LaTeX, and compile a tailored resume PDF."""
        if not bool(getattr(self._settings, "resume_curation_enabled", True)):
            raise ValidationError("Resume curation is disabled")

        user = self.users.get(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found")

        job = JobService(self.session).get(job_id, user_id)
        profile_service = ProfileService(self.session)
        profile = profile_service.get_for_apply(user_id)
        if not profile.exists:
            raise ValidationError("Save an application profile before generating a resume")

        bundle = profile_service.get_resume_template_bundle(user_id)
        ctx = ResumeCurationContext(
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
                "resume for job %s: scraped posting fields matched injection "
                "patterns; forcing heuristic curator",
                job_id,
            )
            requested = "heuristic"

        fields, provider, fallback = self._curate_fields(requested, user, ctx)
        if bundle is not None:
            rendered_files = render_template_bundle(bundle, fields)
            pdf_bytes = self._compile_bundle(rendered_files, bundle.entrypoint)
        else:
            template_tex = (
                profile_service.get_resume_template_tex(user_id) or default_template_tex()
            )
            rendered = render_resume_template(template_tex, fields)
            pdf_bytes = self._compile_pdf(rendered)
        self._validate_pdf(pdf_bytes)

        filename = _tailored_filename(job.company, job.title)
        digest = hashlib.sha256(pdf_bytes).hexdigest()
        artifact = ApplicationArtifactService(self.session).store_tailored_resume_pdf(
            user_id,
            data=pdf_bytes,
            filename=filename,
        )
        return {
            "filename": filename,
            "size_bytes": len(pdf_bytes),
            "content_sha256": digest,
            "pdf_b64": base64.b64encode(pdf_bytes).decode("ascii"),
            "artifact_id": artifact.id,
            "provider": provider,
            "fallback": fallback,
            "injection_guarded": injection,
        }

    def _scraped_fields_look_injected(self, ctx: ResumeCurationContext) -> bool:
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

    def _curate_fields(
        self,
        requested: str,
        user: User,
        ctx: ResumeCurationContext,
    ) -> tuple[CuratedResumeFields, str, bool]:
        if requested != "heuristic":
            try:
                return self._curate_with(requested, user, ctx), requested, False
            except Exception as exc:
                logger.warning("resume curator %s failed: %s", requested, exc)
        return self._curate_with("heuristic", user, ctx), "heuristic", requested != "heuristic"

    def _resolve_provider(self, user: User) -> str:
        if not PlanLimitsService(self.session).allows_summaries(user.id):
            return "heuristic"
        runtime = resolve_ai_settings(self._settings, user, "resume_curation")
        provider = str(runtime.summary_provider)
        if provider in LLM_PROVIDERS:
            return provider
        return "heuristic"

    def _curate_with(
        self,
        provider: str,
        user: User,
        ctx: ResumeCurationContext,
    ) -> CuratedResumeFields:
        runtime = resolve_ai_settings(self._settings, user, "resume_curation")
        curator = self._factory(provider, runtime)
        return curator.curate(ctx)

    def _compile_pdf(self, source: str) -> bytes:
        if self._compile is compile_latex_to_pdf:
            timeout = float(getattr(self._settings, "resume_compile_timeout_seconds", 60.0))
            return compile_latex_to_pdf(source, timeout=timeout)
        return self._compile(source)

    def _compile_bundle(self, files: dict[str, bytes], entrypoint: str) -> bytes:
        if self._bundle_compile is None:
            return self._default_bundle_compile(files, entrypoint)
        return self._bundle_compile(files, entrypoint)

    def _default_bundle_compile(self, files: dict[str, bytes], entrypoint: str) -> bytes:
        timeout = float(getattr(self._settings, "resume_compile_timeout_seconds", 60.0))
        return compile_latex_workspace(files, entrypoint=entrypoint, timeout=timeout)

    def _validate_pdf(self, data: bytes) -> None:
        max_bytes = int(getattr(self._settings, "profile_resume_max_bytes", 2_097_152))
        if len(data) == 0:
            raise ValidationError("Compiled resume PDF is empty")
        if len(data) > max_bytes:
            raise ValidationError("Compiled resume PDF exceeds the upload size limit")
        if not data.startswith(b"%PDF"):
            raise ValidationError("LaTeX compile did not produce a valid PDF")


def _tailored_filename(company: str, title: str) -> str:
    slug = "-".join(part for part in (company.strip(), title.strip()) if part)
    slug = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in slug).strip("-")
    if not slug:
        slug = "tailored"
    if len(slug) > 80:
        slug = slug[:80].rstrip("-")
    return f"resume-{slug}.pdf"
