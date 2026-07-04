"""Compile LaTeX source into a PDF using tectonic or pdflatex."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.core.exceptions import ValidationError

_COMPILER_ENV = {
    "openin_any": "p",
    "openout_any": "p",
    "shell_escape": "f",
}


def compile_latex_to_pdf(
    source: str,
    *,
    commands: tuple[str, ...] | None = None,
    timeout: float = 60.0,
) -> bytes:
    """Render LaTeX source to PDF bytes using an installed compiler."""
    return compile_latex_workspace(
        {"resume.tex": source.encode("utf-8")},
        entrypoint="resume.tex",
        commands=commands,
        timeout=timeout,
    )


def compile_latex_workspace(
    files: dict[str, bytes],
    *,
    entrypoint: str,
    commands: tuple[str, ...] | None = None,
    timeout: float = 60.0,
) -> bytes:
    """Render a multi-file LaTeX workspace to PDF bytes."""
    if entrypoint not in files:
        raise ValidationError(f"LaTeX entrypoint not found in template bundle: {entrypoint}")

    tried: list[str] = []
    last_error = ""
    for cmd in commands or _default_commands():
        exe = shutil.which(cmd)
        if exe is None:
            tried.append(f"{cmd} (not installed)")
            continue
        try:
            pdf = _run_compiler_workspace(exe, cmd, files, entrypoint, timeout=timeout)
            if pdf is not None:
                return pdf
            last_error = f"{cmd} did not produce {entrypoint.replace('.tex', '.pdf')}"
        except subprocess.TimeoutExpired:
            last_error = f"{cmd} timed out after {timeout:.0f}s"
        except OSError as exc:
            last_error = f"{cmd}: {exc}"
        tried.append(cmd)

    detail = last_error or "; ".join(tried) or "no compiler available"
    raise ValidationError(
        "Could not compile the resume PDF. Install tectonic or pdflatex for local dev. "
        f"Details: {detail}"
    )


def _default_commands() -> tuple[str, ...]:
    return ("tectonic", "pdflatex")


def _compiler_env() -> dict[str, str]:
    """Return a minimal environment for LaTeX subprocesses."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "HOME", "TMPDIR", "TEMP", "TMP", "LANG", "LC_ALL"}
    }
    env.update(_COMPILER_ENV)
    return env


def _run_compiler_workspace(
    exe: str,
    cmd: str,
    files: dict[str, bytes],
    entrypoint: str,
    *,
    timeout: float,
) -> bytes | None:
    with tempfile.TemporaryDirectory(prefix="headstart-resume-") as tmp:
        tmp_path = Path(tmp)
        for rel_path, data in files.items():
            out_path = tmp_path / rel_path
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(data)
        tex_path = tmp_path / entrypoint
        env = _compiler_env()
        if cmd == "tectonic":
            proc = subprocess.run(
                [exe, "--outdir", str(tex_path.parent), str(tex_path)],
                capture_output=True,
                timeout=timeout,
                text=True,
                check=False,
                env=env,
            )
        else:
            proc = subprocess.run(
                [
                    exe,
                    "-interaction=nonstopmode",
                    "-no-shell-escape",
                    "-output-directory",
                    str(tex_path.parent),
                    str(tex_path.name),
                ],
                capture_output=True,
                timeout=timeout,
                text=True,
                check=False,
                cwd=tex_path.parent,
                env=env,
            )
        if proc.returncode != 0:
            stderr = (proc.stderr or proc.stdout or "").strip()
            raise ValidationError(stderr or f"{cmd} failed with exit code {proc.returncode}")
        pdf_name = entrypoint.replace(".tex", ".pdf")
        pdf_path = tex_path.parent / pdf_name
        if not pdf_path.is_file():
            return None
        return pdf_path.read_bytes()
