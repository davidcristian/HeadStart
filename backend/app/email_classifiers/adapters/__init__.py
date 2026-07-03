"""Email classifier adapter discovery."""

from app.email_classifiers.adapters import anthropic as _anthropic  # noqa: F401
from app.email_classifiers.adapters import gemini as _gemini  # noqa: F401
from app.email_classifiers.adapters import heuristic as _heuristic  # noqa: F401
from app.email_classifiers.adapters import llamacpp as _llamacpp  # noqa: F401
from app.email_classifiers.adapters import openai as _openai  # noqa: F401
