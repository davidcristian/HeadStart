"""Importing this package registers all built-in apply adapters.

Add a new adapter by creating a module here and importing it below. Nothing
else in the codebase needs to change (see docs/recipes.md).
"""

from app.appliers.adapters import (
    amazon_jobs,
    ashby,
    google_careers,
    greenhouse,
    indeed,
    lever,
    microsoft_careers,
    workday,
)

__all__ = [
    "amazon_jobs",
    "ashby",
    "google_careers",
    "greenhouse",
    "indeed",
    "lever",
    "microsoft_careers",
    "workday",
]
