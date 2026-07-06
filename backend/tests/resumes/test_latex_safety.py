"""Tests for uploaded LaTeX safety checks."""

from __future__ import annotations

import pytest

from app.core.exceptions import ValidationError
from app.resumes.latex_safety import is_scanned_bundle_member, reject_dangerous_latex_content


@pytest.mark.parametrize(
    ("tex", "label"),
    [
        (r"\input{/etc/passwd}", "absolute-input"),
        (r"\input{ /etc/passwd}", "absolute-input-spaced"),
        (r"\input /etc/passwd", "absolute-input-braceless"),
        (r"\input{../secret.tex}", "parent-input"),
        (r"\input ../secret.tex", "parent-input-braceless"),
        (r"\include{|whoami}", "pipe-include"),
        (r"\include{../other.tex}", "parent-include"),
        (r"\openin 5=/etc/passwd", "openin"),
        (r"\read 5 to \foo", "read"),
        (r"\input{~/.ssh/id_rsa}", "home-input"),
        (r"\input ~/.bashrc", "home-input-braceless"),
        (r"\write18{rm -rf /}", "write18"),
        (r"\immediate\write18{uname -a}", "immediate-write18"),
    ],
)
def test_reject_dangerous_latex_content_blocks_shell_and_file_access(tex: str, label: str) -> None:
    with pytest.raises(ValidationError, match="disallowed LaTeX commands"):
        reject_dangerous_latex_content(tex, label=label)


def test_reject_dangerous_latex_content_allows_safe_markup() -> None:
    reject_dangerous_latex_content(
        r"\documentclass{article}\input{section}\begin{document}Hello\end{document}",
        label="safe.tex",
    )


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("main.tex", True),
        ("pkg/style.sty", True),
        ("resume.cls", True),
        ("photo.png", False),
        ("refs.bib", False),
    ],
)
def test_is_scanned_bundle_member(path: str, expected: bool) -> None:
    assert is_scanned_bundle_member(path) is expected
