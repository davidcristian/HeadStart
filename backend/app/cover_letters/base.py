"""Cover letter generator base class and registry."""

from abc import ABC, abstractmethod

from app.ai.registry import AdapterRegistry
from app.cover_letters.types import CoverLetterContext


class CoverLetterGenerator(ABC):
    """Produce a cover letter for one job application."""

    @abstractmethod
    def generate(self, ctx: CoverLetterContext) -> str:
        """Return cover letter text; raise on unrecoverable failure."""
        raise NotImplementedError


_registry: AdapterRegistry[CoverLetterGenerator] = AdapterRegistry(
    noun="cover letter generator", adapters_module="app.cover_letters.adapters"
)
register_cover_letter_generator = _registry.register
get_cover_letter_generator = _registry.get
available_cover_letter_generators = _registry.available
