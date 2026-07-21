"""Tests for LaTeX PDF compilation helpers."""

import resource
import subprocess
from pathlib import Path

import pytest

from app.core.exceptions import ValidationError
from app.resumes.compile import (
    _COMPILER_RLIMIT_AS_BYTES,
    _COMPILER_RLIMIT_NPROC,
    _compiler_env,
    _compiler_preexec,
    _run_compiler_workspace,
    _try_set_rlimit,
    compile_latex_to_pdf,
    compile_latex_workspace,
)


class _FakeProc:
    def __init__(self, returncode: int = 0, stderr: str = "", stdout: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = stdout


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


def test_compile_latex_workspace_reports_timeout(monkeypatch) -> None:
    monkeypatch.setattr("app.resumes.compile.shutil.which", lambda cmd: f"/usr/bin/{cmd}")

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="tectonic", timeout=1.0)

    monkeypatch.setattr("app.resumes.compile._run_compiler_workspace", timeout)
    with pytest.raises(ValidationError, match="timed out"):
        compile_latex_workspace({"main.tex": b"tex"}, entrypoint="main.tex", commands=("tectonic",))


def test_compile_latex_workspace_reports_oserror(monkeypatch) -> None:
    monkeypatch.setattr("app.resumes.compile.shutil.which", lambda cmd: f"/usr/bin/{cmd}")

    def oserror(*args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr("app.resumes.compile._run_compiler_workspace", oserror)
    with pytest.raises(ValidationError, match="permission denied"):
        compile_latex_workspace({"main.tex": b"tex"}, entrypoint="main.tex", commands=("tectonic",))


def test_compiler_env_allowlists_runtime_keys_only(monkeypatch) -> None:
    """Compiler children must not inherit app secrets."""
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("HOME", "/home/headstart")
    monkeypatch.setenv("TMPDIR", "/tmp")
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("JWT_SECRET", "should-not-reach-compiler")
    monkeypatch.setenv("CREDENTIALS_SECRET_KEY", "should-not-reach-compiler")
    monkeypatch.setenv("POSTGRES_PASSWORD", "should-not-reach-compiler")
    monkeypatch.setenv("OPENAI_API_KEY", "should-not-reach-compiler")
    monkeypatch.setenv("TEXMFHOME", "/should-not-reach-compiler")

    env = _compiler_env()
    assert env["PATH"] == "/usr/bin"
    assert env["HOME"] == "/home/headstart"
    assert env["TMPDIR"] == "/tmp"
    assert env["LANG"] == "C.UTF-8"
    assert env["openin_any"] == "p"
    assert env["openout_any"] == "p"
    assert env["shell_escape"] == "f"
    assert "JWT_SECRET" not in env
    assert "CREDENTIALS_SECRET_KEY" not in env
    assert "POSTGRES_PASSWORD" not in env
    assert "OPENAI_API_KEY" not in env
    assert "TEXMFHOME" not in env


def test_run_compiler_workspace_tectonic_success(monkeypatch, tmp_path) -> None:
    captured_env: dict[str, str] = {}

    def fake_run(cmd_args, **kwargs):
        # tectonic invocation: [exe, "--outdir", dir, texpath]
        assert cmd_args[1] == "--outdir"
        captured_env.update(kwargs.get("env", {}))
        assert "JWT_SECRET" not in captured_env
        assert "CREDENTIALS_SECRET_KEY" not in captured_env
        out_dir = Path(cmd_args[2])
        (out_dir / "main.pdf").write_bytes(b"%PDF-tectonic")
        return _FakeProc(returncode=0)

    monkeypatch.setenv("JWT_SECRET", "should-not-reach-compiler")
    monkeypatch.setenv("CREDENTIALS_SECRET_KEY", "should-not-reach-compiler")
    monkeypatch.setattr("app.resumes.compile.subprocess.run", fake_run)
    pdf = _run_compiler_workspace(
        "/usr/bin/tectonic",
        "tectonic",
        {"main.tex": b"content", "sub/part.tex": b"part"},
        "main.tex",
        timeout=5.0,
    )
    assert pdf == b"%PDF-tectonic"
    assert captured_env["openin_any"] == "p"
    assert captured_env["openout_any"] == "p"
    assert captured_env["shell_escape"] == "f"


def test_run_compiler_workspace_pdflatex_success(monkeypatch) -> None:
    """pdflatex must disable shell-escape and pin a restricted TeX open policy."""
    captured_env: dict[str, str] = {}

    def fake_run(cmd_args, **kwargs):
        # pdflatex invocation uses -output-directory and cwd.
        assert "-interaction=nonstopmode" in cmd_args
        assert "-no-shell-escape" in cmd_args
        captured_env.update(kwargs.get("env", {}))
        assert "JWT_SECRET" not in captured_env
        assert "CREDENTIALS_SECRET_KEY" not in captured_env
        out_dir = Path(kwargs["cwd"])
        (out_dir / "main.pdf").write_bytes(b"%PDF-pdflatex")
        return _FakeProc(returncode=0)

    monkeypatch.setenv("JWT_SECRET", "should-not-reach-compiler")
    monkeypatch.setenv("CREDENTIALS_SECRET_KEY", "should-not-reach-compiler")
    monkeypatch.setattr("app.resumes.compile.subprocess.run", fake_run)
    pdf = _run_compiler_workspace(
        "/usr/bin/pdflatex",
        "pdflatex",
        {"main.tex": b"content"},
        "main.tex",
        timeout=5.0,
    )
    assert pdf == b"%PDF-pdflatex"
    assert captured_env["openin_any"] == "p"
    assert captured_env["openout_any"] == "p"
    assert captured_env["shell_escape"] == "f"


def test_run_compiler_workspace_raises_on_nonzero_exit(monkeypatch) -> None:
    def fake_run(cmd_args, **kwargs):
        return _FakeProc(returncode=1, stderr="! LaTeX Error")

    monkeypatch.setattr("app.resumes.compile.subprocess.run", fake_run)
    with pytest.raises(ValidationError, match="LaTeX Error"):
        _run_compiler_workspace(
            "/usr/bin/tectonic", "tectonic", {"main.tex": b"x"}, "main.tex", timeout=5.0
        )


def test_run_compiler_workspace_nonzero_exit_without_output_uses_code(monkeypatch) -> None:
    def fake_run(cmd_args, **kwargs):
        return _FakeProc(returncode=2, stderr="", stdout="")

    monkeypatch.setattr("app.resumes.compile.subprocess.run", fake_run)
    with pytest.raises(ValidationError, match="exit code 2"):
        _run_compiler_workspace(
            "/usr/bin/tectonic", "tectonic", {"main.tex": b"x"}, "main.tex", timeout=5.0
        )


def test_run_compiler_workspace_derives_pdf_name_from_final_suffix_only(monkeypatch) -> None:
    # entrypoint.replace(".tex", ".pdf") would mis-derive "report.tex.tex" as
    # "report.pdf.pdf"; only the trailing suffix must swap.
    def fake_run(cmd_args, **kwargs):
        out_dir = Path(cmd_args[2])
        (out_dir / "report.tex.pdf").write_bytes(b"%PDF-suffix")
        return _FakeProc(returncode=0)

    monkeypatch.setattr("app.resumes.compile.subprocess.run", fake_run)
    pdf = _run_compiler_workspace(
        "/usr/bin/tectonic",
        "tectonic",
        {"report.tex.tex": b"content"},
        "report.tex.tex",
        timeout=5.0,
    )
    assert pdf == b"%PDF-suffix"


def test_run_compiler_workspace_returns_none_when_pdf_missing(monkeypatch) -> None:
    def fake_run(cmd_args, **kwargs):
        return _FakeProc(returncode=0)  # succeeds but writes no PDF

    monkeypatch.setattr("app.resumes.compile.subprocess.run", fake_run)
    result = _run_compiler_workspace(
        "/usr/bin/tectonic", "tectonic", {"main.tex": b"x"}, "main.tex", timeout=5.0
    )
    assert result is None


def test_run_compiler_workspace_passes_rlimit_preexec_on_posix(monkeypatch) -> None:
    """Compiler children get AS/CPU/NPROC rlimits via preexec_fn."""
    captured: dict[str, object] = {}

    def fake_run(cmd_args, **kwargs):
        captured["preexec_fn"] = kwargs.get("preexec_fn")
        out_dir = Path(cmd_args[2])
        (out_dir / "main.pdf").write_bytes(b"%PDF-rlimit")
        return _FakeProc(returncode=0)

    monkeypatch.setattr("app.resumes.compile._posix_rlimits_supported", lambda: True)
    monkeypatch.setattr("app.resumes.compile.subprocess.run", fake_run)
    pdf = _run_compiler_workspace(
        "/usr/bin/tectonic", "tectonic", {"main.tex": b"x"}, "main.tex", timeout=7.2
    )
    assert pdf == b"%PDF-rlimit"
    preexec = captured["preexec_fn"]
    assert callable(preexec)

    calls: list[tuple[int, tuple[int, int]]] = []

    def fake_getrlimit(which: int) -> tuple[int, int]:
        return (resource.RLIM_INFINITY, resource.RLIM_INFINITY)

    def fake_setrlimit(which: int, limits: tuple[int, int]) -> None:
        calls.append((which, limits))

    monkeypatch.setattr("app.resumes.compile.resource.getrlimit", fake_getrlimit)
    monkeypatch.setattr("app.resumes.compile.resource.setrlimit", fake_setrlimit)
    preexec()
    by_which = dict(calls)
    assert by_which[resource.RLIMIT_AS] == (_COMPILER_RLIMIT_AS_BYTES, _COMPILER_RLIMIT_AS_BYTES)
    assert by_which[resource.RLIMIT_CPU] == (8, 8)  # ceil(7.2)
    assert by_which[resource.RLIMIT_NPROC] == (_COMPILER_RLIMIT_NPROC, _COMPILER_RLIMIT_NPROC)


def test_run_compiler_workspace_omits_preexec_on_non_posix(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(cmd_args, **kwargs):
        captured["preexec_fn"] = kwargs.get("preexec_fn")
        out_dir = Path(kwargs["cwd"])
        (out_dir / "main.pdf").write_bytes(b"%PDF-win")
        return _FakeProc(returncode=0)

    monkeypatch.setattr("app.resumes.compile._posix_rlimits_supported", lambda: False)
    monkeypatch.setattr("app.resumes.compile.subprocess.run", fake_run)
    pdf = _run_compiler_workspace(
        "/usr/bin/pdflatex", "pdflatex", {"main.tex": b"x"}, "main.tex", timeout=5.0
    )
    assert pdf == b"%PDF-win"
    assert captured["preexec_fn"] is None


def test_try_set_rlimit_caps_to_finite_hard(monkeypatch) -> None:
    calls: list[tuple[int, tuple[int, int]]] = []
    monkeypatch.setattr(
        "app.resumes.compile.resource.getrlimit",
        lambda which: (100, 200),
    )
    monkeypatch.setattr(
        "app.resumes.compile.resource.setrlimit",
        lambda which, limits: calls.append((which, limits)),
    )
    _try_set_rlimit(resource.RLIMIT_CPU, 500)
    assert calls == [(resource.RLIMIT_CPU, (200, 200))]


def test_try_set_rlimit_keeps_ceiling_below_hard(monkeypatch) -> None:
    calls: list[tuple[int, tuple[int, int]]] = []
    monkeypatch.setattr(
        "app.resumes.compile.resource.getrlimit",
        lambda which: (100, 200),
    )
    monkeypatch.setattr(
        "app.resumes.compile.resource.setrlimit",
        lambda which, limits: calls.append((which, limits)),
    )
    _try_set_rlimit(resource.RLIMIT_CPU, 50)
    assert calls == [(resource.RLIMIT_CPU, (50, 200))]


def test_try_set_rlimit_ignores_getrlimit_errors(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.resumes.compile.resource.getrlimit",
        lambda which: (_ for _ in ()).throw(OSError("unsupported")),
    )
    _try_set_rlimit(resource.RLIMIT_AS, 1)  # must not raise


def test_try_set_rlimit_ignores_setrlimit_errors(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.resumes.compile.resource.getrlimit",
        lambda which: (resource.RLIM_INFINITY, resource.RLIM_INFINITY),
    )
    monkeypatch.setattr(
        "app.resumes.compile.resource.setrlimit",
        lambda which, limits: (_ for _ in ()).throw(ValueError("denied")),
    )
    _try_set_rlimit(resource.RLIMIT_NPROC, 10)  # must not raise


def test_compiler_preexec_cpu_seconds_at_least_one(monkeypatch) -> None:
    calls: list[tuple[int, tuple[int, int]]] = []
    monkeypatch.setattr(
        "app.resumes.compile.resource.getrlimit",
        lambda which: (resource.RLIM_INFINITY, resource.RLIM_INFINITY),
    )
    monkeypatch.setattr(
        "app.resumes.compile.resource.setrlimit",
        lambda which, limits: calls.append((which, limits)),
    )
    _compiler_preexec(0.1)()
    cpu = next(lim for which, lim in calls if which == resource.RLIMIT_CPU)
    assert cpu == (1, 1)
