"""LaTeX upload safety checks for resume templates."""

from __future__ import annotations

import re

from app.core.exceptions import ValidationError

_DANGEROUS_LATEX_PATTERNS = (
    re.compile(r"\\write18\b", re.IGNORECASE),
    re.compile(r"\\immediate\\write18\b", re.IGNORECASE),
    re.compile(r"\\openin\b", re.IGNORECASE),
    re.compile(r"\\input\s*\{[|/]", re.IGNORECASE),
    re.compile(r"\\include\s*\{[|/]", re.IGNORECASE),
)


def reject_dangerous_latex_content(tex: str, *, label: str) -> None:
    """Reject uploaded LaTeX that can read arbitrary files or invoke shell escape."""
    for pattern in _DANGEROUS_LATEX_PATTERNS:
        if pattern.search(tex):
            raise ValidationError(
                f"Resume template {label} contains disallowed LaTeX commands."
            )
