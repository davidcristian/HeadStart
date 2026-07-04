"""Tests for LaTeX resume template rendering."""

from app.resumes.fields import heuristic_fields
from app.resumes.template import default_template_tex, render_resume_template
from app.resumes.types import CuratedResumeFields, ResumeCurationContext
from app.schemas.profile import ProfileData, WorkExperienceEntry


def test_render_resume_template_substitutes_placeholders() -> None:
    tex = r"\name{[[full_name]]} \skills{[[skills]]}"
    fields = CuratedResumeFields(full_name="Ada Lovelace", skills="Python, SQL")
    rendered = render_resume_template(tex, fields)
    assert r"\name{Ada Lovelace}" in rendered
    assert r"\skills{Python, SQL}" in rendered


def test_render_resume_template_escapes_latex_special_chars() -> None:
    tex = "[[company]]"
    fields = CuratedResumeFields(company="A&B 100%")
    rendered = render_resume_template(tex, fields)
    assert rendered == r"A\&B 100\%"


def test_render_resume_template_preserves_experience_markup_verbatim() -> None:
    # The experience field carries controlled LaTeX (\item / \textbf); escaping it
    # would strip the \item rows the itemize environment requires (audit AIA-01).
    fields = CuratedResumeFields(experience=r"\item \textbf{Engineer, ACME} — Built APIs")
    rendered = render_resume_template("[[experience]]", fields)
    assert rendered == r"\item \textbf{Engineer, ACME} — Built APIs"
    assert r"\textbackslash{}item" not in rendered


def test_render_default_template_with_heuristic_fields_keeps_itemize_items() -> None:
    # End-to-end regression: the default template wraps [[experience]] in an
    # itemize, so the substituted content must still contain real \item rows.
    ctx = ResumeCurationContext(
        job_title="Engineer",
        company="ACME",
        profile=ProfileData(
            full_name="Ada Lovelace",
            work_experience=[WorkExperienceEntry(job_title="Engineer", company="Example Corp")],
        ),
    )
    rendered = render_resume_template(default_template_tex(), heuristic_fields(ctx))
    assert r"\begin{itemize}" in rendered
    assert r"\item \textbf{Engineer, Example Corp}" in rendered
    assert r"\textbackslash{}item" not in rendered


def test_default_template_tex_loads_builtin_template() -> None:
    tex = default_template_tex()
    assert "[[full_name]]" in tex
    # lru_cache returns the same object on repeat calls.
    assert default_template_tex() is tex
