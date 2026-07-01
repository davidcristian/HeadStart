"""Importing this package registers all built-in apply adapters.

Add a new adapter by creating a module here and importing it below. Nothing
else in the codebase needs to change (see docs/recipes.md).
"""

from app.appliers.adapters import ashby, greenhouse, lever

__all__ = ["ashby", "greenhouse", "lever"]
