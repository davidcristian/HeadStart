"""Importing this package registers all built-in summarizer adapters.

Add a provider by creating a module here and importing it below (see
docs/recipes.md).
"""

from app.summarizers.adapters import heuristic, openai

__all__ = ["heuristic", "openai"]
