"""LaTeX resume template rendering and defaults."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.resumes.types import CuratedResumeFields

_PLACEHOLDER_KEYS = (
    "full_name",
    "email",
    "phone",
    "location",
    "linkedin",
    "github",
    "website",
    "job_title",
    "company",
    "summary",
    "experience",
    "education",
    "skills",
)

# Fields whose curated value is controlled LaTeX markup (\item / \textbf rows the
# default template wraps in an itemize) rather than free text. Escaping them would
# neutralize the very structure the template depends on — the heuristic and LLM
# paths both emit this markup and are responsible for escaping their own free-text
# parts. Every other placeholder is a free-text / PII scalar and is escaped here.
_RAW_LATEX_KEYS = frozenset({"experience"})


def render_resume_template(tex: str, fields: CuratedResumeFields) -> str:
    """Substitute [[key]] placeholders in a LaTeX resume template."""
    values = fields.model_dump()
    result = tex
    for key in _PLACEHOLDER_KEYS:
        token = f"[[{key}]]"
        value = str(values.get(key, "") or "")
        if key not in _RAW_LATEX_KEYS:
            value = escape_latex(value)
        result = result.replace(token, value)
    return result


def escape_latex(value: str) -> str:
    """Escape characters that break LaTeX when substituted into text mode."""
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    out: list[str] = []
    for char in value:
        out.append(replacements.get(char, char))
    return "".join(out)


@lru_cache(maxsize=1)
def default_template_tex() -> str:
    """Built-in resume template used when the user has not uploaded one."""
    path = Path(__file__).resolve().parent / "default_template.tex"
    return path.read_text(encoding="utf-8")
