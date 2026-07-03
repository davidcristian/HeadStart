"""Placeholder substitution for cover-letter templates."""


def render_cover_letter_template(template: str, *, company: str, job_title: str) -> str:
    """Substitute simple placeholders in a cover-letter template."""
    replacements = {
        "{company}": company,
        "{job_title}": job_title,
        "{title}": job_title,
    }
    result = template
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)
    return result
