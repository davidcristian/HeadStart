"""AI task purposes that can each pick a provider/model."""

from typing import Literal

AiPurposeId = Literal[
    "summary",
    "cover_letter",
    "resume_curation",
    "email_classify",
    "email_draft",
]

AI_PURPOSES: tuple[AiPurposeId, ...] = (
    "summary",
    "cover_letter",
    "resume_curation",
    "email_classify",
    "email_draft",
)

# Purposes users can override independently of the global default.
OVERRIDABLE_AI_PURPOSES: tuple[AiPurposeId, ...] = (
    "cover_letter",
    "resume_curation",
    "email_classify",
    "email_draft",
)
