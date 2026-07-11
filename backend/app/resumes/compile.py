"""Compile LaTeX source into a PDF using tectonic or pdflatex."""

from __future__ import annotations

import math
import os
import resource
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from app.core.exceptions import ValidationError

_COMPILER_ENV = {
    "openin_any": "p",
    "openout_any": "p",
    "shell_escape": "f",
}

# Soft ceilings for the compiler child (AIA-10). NPROC is high enough not to
# collide with a busy Celery worker UID while still bounding fork bombs.
_COMPILER_RLIMIT_AS_BYTES = 512 * 1024 * 1024
_COMPILER_RLIMIT_NPROC = 512


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
            last_error = f"{cmd} did not produce {_pdf_output_name(entrypoint)}"
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


def _pdf_output_name(entrypoint: str) -> str:
    """Compiler PDF output name for a .tex entrypoint (only the final suffix swaps)."""
    return Path(entrypoint).with_suffix(".pdf").name


def _compiler_env() -> dict[str, str]:
    """Return a minimal environment for LaTeX subprocesses."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "HOME", "TMPDIR", "TEMP", "TMP", "LANG", "LC_ALL"}
    }
    env.update(_COMPILER_ENV)
    return env


def _posix_rlimits_supported() -> bool:
    """Whether compiler children can receive preexec_fn rlimits."""
    return os.name == "posix"


def _try_set_rlimit(which: int, ceiling: int) -> None:
    """Lower a resource soft ceiling for the compiler child when the OS allows it."""
    try:
        _soft, hard = resource.getrlimit(which)
    except (OSError, ValueError):
        return
    limit = ceiling
    if hard != resource.RLIM_INFINITY:
        limit = min(limit, hard)
    new_hard = hard if hard != resource.RLIM_INFINITY else limit
    try:
        resource.setrlimit(which, (limit, new_hard))
    except (OSError, ValueError):
        return


def _compiler_preexec(timeout: float) -> Callable[[], None]:
    """Build a preexec_fn that applies AS/CPU/NPROC rlimits (AIA-10)."""
    cpu_seconds = max(1, math.ceil(timeout))

    def _apply_compiler_rlimits() -> None:
        _try_set_rlimit(resource.RLIMIT_AS, _COMPILER_RLIMIT_AS_BYTES)
        _try_set_rlimit(resource.RLIMIT_CPU, cpu_seconds)
        _try_set_rlimit(resource.RLIMIT_NPROC, _COMPILER_RLIMIT_NPROC)

    return _apply_compiler_rlimits


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
        preexec = _compiler_preexec(timeout) if _posix_rlimits_supported() else None
        if cmd == "tectonic":
            proc = subprocess.run(
                [exe, "--outdir", str(tex_path.parent), str(tex_path)],
                capture_output=True,
                timeout=timeout,
                text=True,
                check=False,
                env=env,
                preexec_fn=preexec,
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
                preexec_fn=preexec,
            )
        if proc.returncode != 0:
            stderr = (proc.stderr or proc.stdout or "").strip()
            raise ValidationError(stderr or f"{cmd} failed with exit code {proc.returncode}")
        pdf_name = _pdf_output_name(entrypoint)
        pdf_path = tex_path.parent / pdf_name
        if not pdf_path.is_file():
            return None
        return pdf_path.read_bytes()
