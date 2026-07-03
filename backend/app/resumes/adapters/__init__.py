"""Importing this package registers all built-in resume curators."""

from app.resumes.adapters import anthropic, gemini, heuristic, llamacpp, openai

__all__ = ["anthropic", "gemini", "heuristic", "llamacpp", "openai"]
