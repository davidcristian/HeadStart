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


def test_parse_template_bundle_rejects_empty_bytes() -> None:
    with pytest.raises(ValidationError, match="is empty"):
        parse_template_bundle(b"")


def test_parse_template_bundle_rejects_bad_zip() -> None:
    with pytest.raises(ValidationError, match="valid .zip"):
        parse_template_bundle(b"not a zip file at all")


def test_parse_template_bundle_rejects_archive_with_only_directories() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("folder/", "")
    with pytest.raises(ValidationError, match="is empty"):
        parse_template_bundle(buf.getvalue())


def test_parse_template_bundle_rejects_too_many_files() -> None:
    data = _zip_files({f"file{i}.tex": "x" for i in range(65)})
    with pytest.raises(ValidationError, match="cannot exceed"):
        parse_template_bundle(data)


def test_parse_template_bundle_rejects_oversized_uncompressed() -> None:
    # A highly compressible 6 MB file blows past the 5 MB uncompressed limit.
    data = _zip_files({"main.tex": b"a" * (6 * 1024 * 1024)})
    with pytest.raises(ValidationError, match="uncompressed size"):
        parse_template_bundle(data)


def test_parse_template_bundle_rejects_absolute_path() -> None:
    data = _zip_files({"/etc/passwd.tex": "bad"})
    with pytest.raises(ValidationError, match="invalid path"):
        parse_template_bundle(data)


def test_parse_template_bundle_rejects_path_that_normalizes_to_empty() -> None:
    # A member whose name is only "." components strips down to no real parts.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        info = zipfile.ZipInfo("./.")
        archive.writestr(info, b"x")
    with pytest.raises(ValidationError, match="invalid path"):
        parse_template_bundle(buf.getvalue())


def test_parse_template_bundle_rejects_duplicate_normalized_path() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("main.tex", b"one")
        archive.writestr("./main.tex", b"two")
    with pytest.raises(ValidationError, match="duplicate path"):
        parse_template_bundle(buf.getvalue())


def test_parse_template_bundle_rejects_size_mismatch(monkeypatch) -> None:
    # Force the read bytes to disagree with the recorded file_size to exercise
    # the defensive size-mismatch guard.
    data = _zip_files({"main.tex": b"hello world"})
    real_read = zipfile.ZipFile.read

    def short_read(self, name):  # type: ignore[no-untyped-def]
        return real_read(self, name)[:-1]

    monkeypatch.setattr(zipfile.ZipFile, "read", short_read)
    with pytest.raises(ValidationError, match="could not read file"):
        parse_template_bundle(data)


def test_parse_template_bundle_resolves_single_tex_entrypoint() -> None:
    data = _zip_files({"cv.tex": "only tex", "logo.png": b"\x89PNG"})
    bundle = parse_template_bundle(data)
    assert bundle.entrypoint == "cv.tex"


def test_parse_template_bundle_requires_at_least_one_tex() -> None:
    data = _zip_files({"logo.png": b"\x89PNG", "style.sty": "x"})
    with pytest.raises(ValidationError, match="at least one .tex"):
        parse_template_bundle(data)


def test_render_template_bundle_rejects_non_utf8_tex() -> None:
    bundle = ResumeTemplateBundle(
        entrypoint="main.tex",
        files={"main.tex": b"\xff\xfe invalid"},
    )
    with pytest.raises(ValidationError, match="valid UTF-8"):
        render_template_bundle(bundle, CuratedResumeFields())
