"""Validate and unpack multi-file LaTeX resume template bundles (.zip)."""

from __future__ import annotations

import io
import posixpath
import zipfile
from dataclasses import dataclass
from typing import Final

from app.core.exceptions import ValidationError
from app.resumes.template import render_resume_template
from app.resumes.types import CuratedResumeFields

ALLOWED_BUNDLE_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".tex",
        ".sty",
        ".cls",
        ".bib",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".pdf",
        ".eps",
        ".svg",
    }
)

ENTRYPOINT_CANDIDATES: Final[tuple[str, ...]] = ("main.tex", "resume.tex")
MAX_BUNDLE_FILES: Final[int] = 64
MAX_BUNDLE_UNCOMPRESSED_BYTES: Final[int] = 5_242_880  # 5 MB


@dataclass(frozen=True)
class ResumeTemplateBundle:
    """Validated LaTeX template bundle ready for placeholder substitution."""

    entrypoint: str
    files: dict[str, bytes]


def parse_template_bundle(zip_bytes: bytes) -> ResumeTemplateBundle:
    """Extract and validate a LaTeX template zip archive."""
    if not zip_bytes:
        raise ValidationError("Resume template bundle is empty")
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            return _read_bundle(archive)
    except zipfile.BadZipFile as exc:
        raise ValidationError("Resume template bundle must be a valid .zip file") from exc


def render_template_bundle(
    bundle: ResumeTemplateBundle,
    fields: CuratedResumeFields,
) -> dict[str, bytes]:
    """Apply [[placeholder]] substitution to every .tex file in the bundle."""
    rendered: dict[str, bytes] = {}
    for path, data in bundle.files.items():
        if not path.lower().endswith(".tex"):
            rendered[path] = data
            continue
        try:
            tex = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationError(f"LaTeX file {path} must be valid UTF-8 text") from exc
        rendered[path] = render_resume_template(tex, fields).encode("utf-8")
    return rendered


def _read_bundle(archive: zipfile.ZipFile) -> ResumeTemplateBundle:
    members = [info for info in archive.infolist() if not info.is_dir()]
    if not members:
        raise ValidationError("Resume template bundle is empty")
    if len(members) > MAX_BUNDLE_FILES:
        raise ValidationError(f"Resume template bundle cannot exceed {MAX_BUNDLE_FILES} files")

    files: dict[str, bytes] = {}
    total_uncompressed = 0
    for info in members:
        rel_path = _normalize_member_path(info.filename)
        ext = posixpath.splitext(rel_path)[1].lower()
        if ext not in ALLOWED_BUNDLE_EXTENSIONS:
            raise ValidationError(
                "Resume template bundle contains a disallowed file type: "
                f"{rel_path} (allowed: {', '.join(sorted(ALLOWED_BUNDLE_EXTENSIONS))})"
            )
        total_uncompressed += info.file_size
        if total_uncompressed > MAX_BUNDLE_UNCOMPRESSED_BYTES:
            raise ValidationError(
                "Resume template bundle uncompressed size exceeds the limit "
                f"({MAX_BUNDLE_UNCOMPRESSED_BYTES // 1_048_576} MB)"
            )
        if rel_path in files:
            raise ValidationError(f"Resume template bundle contains duplicate path: {rel_path}")
        data = archive.read(info)
        if len(data) != info.file_size:
            raise ValidationError(f"Resume template bundle could not read file: {rel_path}")
        files[rel_path] = data

    entrypoint = _resolve_entrypoint(files)
    return ResumeTemplateBundle(entrypoint=entrypoint, files=files)


def _normalize_member_path(raw: str) -> str:
    """Reject path traversal and normalize zip member paths to posix relative paths."""
    cleaned = raw.replace("\\", "/").strip()
    if not cleaned or cleaned.startswith("/"):
        raise ValidationError(f"Resume template bundle has an invalid path: {raw}")
    parts: list[str] = []
    for part in cleaned.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise ValidationError(f"Resume template bundle path traversal is not allowed: {raw}")
        parts.append(part)
    if not parts:
        raise ValidationError(f"Resume template bundle has an invalid path: {raw}")
    return posixpath.join(*parts)


def _resolve_entrypoint(files: dict[str, bytes]) -> str:
    """Pick main.tex, resume.tex, or the only .tex file in the bundle."""
    for candidate in ENTRYPOINT_CANDIDATES:
        if candidate in files:
            return candidate
    tex_paths = sorted(path for path in files if path.lower().endswith(".tex"))
    if len(tex_paths) == 1:
        return tex_paths[0]
    if not tex_paths:
        raise ValidationError("Resume template bundle must include at least one .tex file")
    raise ValidationError(
        "Resume template bundle must include main.tex or resume.tex as the entrypoint"
    )
