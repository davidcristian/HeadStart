"""Repositories: the only place that issues database queries."""

from app.repositories.application_artifacts import ApplicationArtifactRepository
from app.repositories.application_logs import ApplicationLogRepository
from app.repositories.credentials import CredentialRepository
from app.repositories.deliveries import DeliveryLogRepository
from app.repositories.jobs import SeenJobRepository
from app.repositories.searches import SearchRepository
from app.repositories.sources import SourceRepository
from app.repositories.targets import TargetRepository
from app.repositories.users import UserRepository

__all__ = [
    "ApplicationArtifactRepository",
    "ApplicationLogRepository",
    "CredentialRepository",
    "DeliveryLogRepository",
    "SearchRepository",
    "SeenJobRepository",
    "SourceRepository",
    "TargetRepository",
    "UserRepository",
]
