"""Pluggable cover-letter generators for auto-apply."""

from app.cover_letters.base import (
    CoverLetterGenerator,
    available_cover_letter_generators,
    get_cover_letter_generator,
    register_cover_letter_generator,
)
from app.cover_letters.types import CoverLetterContext

__all__ = [
    "CoverLetterContext",
    "CoverLetterGenerator",
    "available_cover_letter_generators",
    "get_cover_letter_generator",
    "register_cover_letter_generator",
]
