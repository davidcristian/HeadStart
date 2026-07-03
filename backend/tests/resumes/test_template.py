"""Tests for LaTeX resume template rendering."""

from app.resumes.template import default_template_tex, render_resume_template
from app.resumes.types import CuratedResumeFields


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


def test_default_template_tex_loads_builtin_template() -> None:
    tex = default_template_tex()
    assert "[[full_name]]" in tex
    # lru_cache returns the same object on repeat calls.
    assert default_template_tex() is tex
