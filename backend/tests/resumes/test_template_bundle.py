"""Tests for multi-file LaTeX resume template bundles."""

from __future__ import annotations

import io
import zipfile

import pytest

from app.core.exceptions import ValidationError
from app.resumes.template_bundle import (
    ResumeTemplateBundle,
    parse_template_bundle,
    render_template_bundle,
)
from app.resumes.types import CuratedResumeFields


def _zip_files(files: dict[str, str | bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for path, content in files.items():
            payload = content.encode("utf-8") if isinstance(content, str) else content
            archive.writestr(path, payload)
    return buf.getvalue()


def test_parse_template_bundle_accepts_main_tex_entrypoint() -> None:
    data = _zip_files(
        {
            "main.tex": r"\documentclass{article}\input{section}\begin{document}Hi\end{document}",
            "section.tex": "Section body",
            "style.sty": r"\ProvidesPackage{style}",
        }
    )
    bundle = parse_template_bundle(data)
    assert bundle.entrypoint == "main.tex"
    assert set(bundle.files) == {"main.tex", "section.tex", "style.sty"}


def test_parse_template_bundle_rejects_path_traversal() -> None:
    data = _zip_files({"../main.tex": "bad"})
    with pytest.raises(ValidationError, match="path traversal"):
        parse_template_bundle(data)


def test_parse_template_bundle_rejects_disallowed_extension() -> None:
    data = _zip_files({"main.tex": "ok", "evil.exe": "nope"})
    with pytest.raises(ValidationError, match="disallowed file type"):
        parse_template_bundle(data)


def test_parse_template_bundle_requires_entrypoint_when_ambiguous() -> None:
    data = _zip_files({"one.tex": "a", "two.tex": "b"})
    with pytest.raises(ValidationError, match="main.tex or resume.tex"):
        parse_template_bundle(data)


def test_render_template_bundle_substitutes_in_all_tex_files() -> None:
    bundle = ResumeTemplateBundle(
        entrypoint="main.tex",
        files={
            "main.tex": b"Name: [[full_name]]",
            "section.tex": b"Role: [[job_title]]",
            "style.sty": b"static",
        },
    )
    rendered = render_template_bundle(
        bundle,
        CuratedResumeFields(full_name="Ada", job_title="Engineer"),
    )
    assert rendered["main.tex"] == b"Name: Ada"
    assert rendered["section.tex"] == b"Role: Engineer"
    assert rendered["style.sty"] == b"static"
