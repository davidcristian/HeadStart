"""Email classifier base class and registry."""

from abc import ABC, abstractmethod

from app.ai.registry import AdapterRegistry
from app.email_classifiers.types import EmailClassificationResult, EmailClassifyContext


class EmailClassifier(ABC):
    """Classify one inbound recruiter email."""

    @abstractmethod
    def classify(self, ctx: EmailClassifyContext) -> EmailClassificationResult:
        """Return a structured label; raise on unrecoverable failure."""
        raise NotImplementedError


_registry: AdapterRegistry[EmailClassifier] = AdapterRegistry(
    noun="email classifier", adapters_module="app.email_classifiers.adapters"
)
register_email_classifier = _registry.register
get_email_classifier = _registry.get
available_email_classifiers = _registry.available
