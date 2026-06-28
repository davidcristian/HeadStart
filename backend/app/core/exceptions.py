"""Domain exceptions. Services raise these; the API layer maps them to HTTP.

Keeping these framework-agnostic means services never import FastAPI.
"""


class DomainError(Exception):
    """Base class for expected, handled errors."""


class NotFoundError(DomainError):
    """A requested entity does not exist."""


class ValidationError(DomainError):
    """Input is structurally valid but violates a business rule."""


class ConflictError(DomainError):
    """The operation conflicts with current state (e.g. duplicate)."""
