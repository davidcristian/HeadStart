"""Compile LaTeX source into a PDF using tectonic or pdflatex."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from app.core.exceptions import ValidationError


def compile_latex_to_pdf(
    source: str,
    *,
    commands: tuple[str, ...] | None = None,
    timeout: float = 60.0,
) -> bytes:
    """Render LaTeX source to PDF bytes using an installed compiler."""
    tried: list[str] = []
    last_error = ""
    for cmd in commands or _default_commands():
        exe = shutil.which(cmd)
        if exe is None:
            tried.append(f"{cmd} (not installed)")
            continue
        try:
            pdf = _run_compiler(exe, cmd, source, timeout=timeout)
            if pdf is not None:
                return pdf
            last_error = f"{cmd} did not produce resume.pdf"
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


def _run_compiler(
    exe: str,
    cmd: str,
    source: str,
    *,
    timeout: float,
) -> bytes | None:
    with tempfile.TemporaryDirectory(prefix="headstart-resume-") as tmp:
        tmp_path = Path(tmp)
        tex_path = tmp_path / "resume.tex"
        tex_path.write_text(source, encoding="utf-8")
        if cmd == "tectonic":
            proc = subprocess.run(
                [exe, "--outdir", str(tmp_path), str(tex_path)],
                capture_output=True,
                timeout=timeout,
                text=True,
                check=False,
            )
        else:
            proc = subprocess.run(
                [
                    exe,
                    "-interaction=nonstopmode",
                    "-output-directory",
                    str(tmp_path),
                    str(tex_path.name),
                ],
                capture_output=True,
                timeout=timeout,
                text=True,
                check=False,
                cwd=tmp_path,
            )
        if proc.returncode != 0:
            stderr = (proc.stderr or proc.stdout or "").strip()
            raise ValidationError(stderr or f"{cmd} failed with exit code {proc.returncode}")
        pdf_path = tmp_path / "resume.pdf"
        if not pdf_path.is_file():
            return None
        return pdf_path.read_bytes()
