"""Tests for uploaded LaTeX safety checks."""

from __future__ import annotations

import pytest

from app.core.exceptions import ValidationError
from app.resumes.latex_safety import reject_dangerous_latex_content


@pytest.mark.parametrize(
    ("tex", "label"),
    [
        (r"\input{/etc/passwd}", "absolute-input"),
        (r"\include{|whoami}", "pipe-include"),
        (r"\openin 5=/etc/passwd", "openin"),
        (r"\write18{rm -rf /}", "write18"),
        (r"\immediate\write18{uname -a}", "immediate-write18"),
    ],
)
def test_reject_dangerous_latex_content_blocks_shell_and_file_access(
    tex: str, label: str
) -> None:
    with pytest.raises(ValidationError, match="disallowed LaTeX commands"):
        reject_dangerous_latex_content(tex, label=label)


def test_reject_dangerous_latex_content_allows_safe_markup() -> None:
    reject_dangerous_latex_content(
        r"\documentclass{article}\begin{document}Hello\end{document}",
        label="safe.tex",
    )
