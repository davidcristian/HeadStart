"""Importing this package registers all built-in cover-letter generators."""

from app.cover_letters.adapters import anthropic, gemini, heuristic, llamacpp, openai

__all__ = ["anthropic", "gemini", "heuristic", "llamacpp", "openai"]
