"""Reply drafter base class and registry."""

from abc import ABC, abstractmethod

from app.ai.registry import AdapterRegistry
from app.reply_drafters.types import ReplyDraftContext, ReplyDraftResult


class ReplyDrafter(ABC):
    """Draft a recruiter follow-up reply for one classified inbound email."""

    @abstractmethod
    def draft(self, ctx: ReplyDraftContext) -> ReplyDraftResult:
        """Return a reply subject and body; raise on unrecoverable failure."""
        raise NotImplementedError


_registry: AdapterRegistry[ReplyDrafter] = AdapterRegistry(
    noun="reply drafter", adapters_module="app.reply_drafters.adapters"
)
register_reply_drafter = _registry.register
get_reply_drafter = _registry.get
available_reply_drafters = _registry.available
