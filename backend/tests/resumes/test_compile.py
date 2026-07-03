"""Tests for LaTeX PDF compilation helpers."""

import pytest

from app.core.exceptions import ValidationError
from app.resumes.compile import compile_latex_to_pdf, compile_latex_workspace


def test_compile_latex_workspace_rejects_missing_entrypoint() -> None:
    with pytest.raises(ValidationError, match="entrypoint not found"):
        compile_latex_workspace({"other.tex": b"content"}, entrypoint="main.tex")


def test_compile_latex_workspace_returns_pdf_from_compiler(monkeypatch) -> None:
    monkeypatch.setattr("app.resumes.compile.shutil.which", lambda cmd: f"/usr/bin/{cmd}")
    monkeypatch.setattr(
        "app.resumes.compile._run_compiler_workspace",
        lambda *args, **kwargs: b"%PDF-1.4 fake",
    )
    result = compile_latex_workspace(
        {"main.tex": b"\\documentclass{article}\\begin{document}Hi\\end{document}"},
        entrypoint="main.tex",
        commands=("tectonic",),
    )
    assert result == b"%PDF-1.4 fake"


def test_compile_latex_workspace_raises_when_no_compiler_installed(monkeypatch) -> None:
    monkeypatch.setattr("app.resumes.compile.shutil.which", lambda cmd: None)
    with pytest.raises(ValidationError, match="Could not compile"):
        compile_latex_workspace({"main.tex": b"tex"}, entrypoint="main.tex")


def test_compile_latex_workspace_surfaces_compiler_validation_error(monkeypatch) -> None:
    monkeypatch.setattr("app.resumes.compile.shutil.which", lambda cmd: "/usr/bin/pdflatex")

    def fail_compiler(*args, **kwargs) -> bytes:
        raise ValidationError("! LaTeX Error: undefined control sequence")

    monkeypatch.setattr("app.resumes.compile._run_compiler_workspace", fail_compiler)
    with pytest.raises(ValidationError, match="undefined control sequence"):
        compile_latex_workspace({"main.tex": b"\\bad"}, entrypoint="main.tex")


def test_compile_latex_to_pdf_wraps_single_file_workspace(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_workspace(files, *, entrypoint, commands=None, timeout=60.0):
        captured["files"] = files
        captured["entrypoint"] = entrypoint
        return b"%PDF"

    monkeypatch.setattr("app.resumes.compile.compile_latex_workspace", fake_workspace)
    result = compile_latex_to_pdf("\\documentclass{article}")
    assert result == b"%PDF"
    assert captured["entrypoint"] == "resume.tex"
    assert "resume.tex" in captured["files"]


def test_compile_latex_workspace_tries_next_compiler_when_pdf_missing(monkeypatch) -> None:
    calls: list[str] = []

    def which(cmd: str) -> str | None:
        return f"/usr/bin/{cmd}"

    def run_compiler(exe, cmd, files, entrypoint, *, timeout):
        calls.append(cmd)
        if cmd == "tectonic":
            return None
        return b"%PDF-second"

    monkeypatch.setattr("app.resumes.compile.shutil.which", which)
    monkeypatch.setattr("app.resumes.compile._run_compiler_workspace", run_compiler)
    result = compile_latex_workspace({"main.tex": b"tex"}, entrypoint="main.tex")
    assert result == b"%PDF-second"
    assert calls == ["tectonic", "pdflatex"]
