"""Pluggable inbound email classifiers for dev inbox automation."""

from app.email_classifiers.base import (
    EmailClassifier,
    available_email_classifiers,
    get_email_classifier,
    register_email_classifier,
)
from app.email_classifiers.labels import EMAIL_CLASSIFICATION_LABELS, EmailClassificationLabel
from app.email_classifiers.types import (
    EmailClassificationResult,
    EmailClassifyContext,
    LinkedApplicationContext,
)

__all__ = [
    "EMAIL_CLASSIFICATION_LABELS",
    "EmailClassificationLabel",
    "EmailClassificationResult",
    "EmailClassifyContext",
    "EmailClassifier",
    "LinkedApplicationContext",
    "available_email_classifiers",
    "get_email_classifier",
    "register_email_classifier",
]
