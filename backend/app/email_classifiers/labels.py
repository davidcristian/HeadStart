"""Allowlisted inbound email classification labels."""

from typing import Literal

EmailClassificationLabel = Literal[
    "general",
    "rejection",
    "follow_up",
    "interview_request",
    "self_ghost_archive",
    "out_of_scope",
]

EMAIL_CLASSIFICATION_LABELS: frozenset[str] = frozenset(
    {
        "general",
        "rejection",
        "follow_up",
        "interview_request",
        "self_ghost_archive",
        "out_of_scope",
    }
)

GHOST_SUBJECT_PREFIX = "[HeadStart Ghost]"
GHOST_HEADER_TYPE = "X-HeadStart-Type"
GHOST_HEADER_VALUE = "ghost"
