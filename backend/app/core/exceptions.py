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


class UnauthorizedError(DomainError):
    """The caller is missing or has invalid credentials for this resource."""


class PlanLimitError(DomainError):
    """The user's plan does not allow this action (cap reached or feature gated)."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        plan: str,
        limit: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.plan = plan
        self.limit = limit


class RateLimitError(DomainError):
    """Too many requests in the configured window (auth abuse prevention)."""
