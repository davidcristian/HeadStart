"""LaTeX upload safety checks for resume templates."""

from __future__ import annotations

import re
from typing import Final

from app.core.exceptions import ValidationError

# TeX-like members that can carry \\input / shell-escape primitives into the
# compile workspace (packages and classes are loaded by the entrypoint).
SCANNED_BUNDLE_EXTENSIONS: Final[frozenset[str]] = frozenset({".tex", ".sty", ".cls"})

# Absolute, pipe, home, or parent-path file access — plus shell-escape /
# stream-read primitives. Relative same-tree includes like \\input{section}
# remain allowed.
_DANGEROUS_LATEX_PATTERNS = (
    re.compile(r"\\write18\b", re.IGNORECASE),
    re.compile(r"\\immediate\\write18\b", re.IGNORECASE),
    re.compile(r"\\openin\b", re.IGNORECASE),
    re.compile(r"\\read\b", re.IGNORECASE),
    re.compile(r"\\(?:input|include)\s*\{\s*[|/~]", re.IGNORECASE),
    re.compile(r"\\(?:input|include)\s*\{\s*\.\./", re.IGNORECASE),
    re.compile(r"\\(?:input|include)\s+[|/~]", re.IGNORECASE),
    re.compile(r"\\(?:input|include)\s+\.\./", re.IGNORECASE),
)


def is_scanned_bundle_member(path: str) -> bool:
    """Return True when a bundle member is TeX source that must be content-scanned."""
    lower = path.lower()
    return any(lower.endswith(ext) for ext in SCANNED_BUNDLE_EXTENSIONS)


def reject_dangerous_latex_content(tex: str, *, label: str) -> None:
    """Reject uploaded LaTeX that can read arbitrary files or invoke shell escape."""
    for pattern in _DANGEROUS_LATEX_PATTERNS:
        if pattern.search(tex):
            raise ValidationError(f"Resume template {label} contains disallowed LaTeX commands.")
