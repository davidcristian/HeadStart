"""Resume curator base class and registry."""

from abc import ABC, abstractmethod

from app.ai.registry import AdapterRegistry
from app.resumes.types import CuratedResumeFields, ResumeCurationContext


class ResumeCurator(ABC):
    """Tailor resume placeholder values for one job application."""

    @abstractmethod
    def curate(self, ctx: ResumeCurationContext) -> CuratedResumeFields:
        """Return curated placeholder values; raise on unrecoverable failure."""
        raise NotImplementedError


_registry: AdapterRegistry[ResumeCurator] = AdapterRegistry(
    noun="resume curator", adapters_module="app.resumes.adapters"
)
register_resume_curator = _registry.register
get_resume_curator = _registry.get
available_resume_curators = _registry.available
