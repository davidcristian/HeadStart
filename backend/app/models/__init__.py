"""ORM models. Importing this package registers every table on `Base.metadata`,
which Alembic autogenerate and `create_all` (tests) rely on.
"""

from app.models.application_log import ApplicationLog
from app.models.application_profile import ApplicationProfile
from app.models.base import Base
from app.models.delivery_log import DeliveryLog
from app.models.notification_target import NotificationTarget
from app.models.password_reset_token import PasswordResetToken
from app.models.pending_digest import PendingDigest
from app.models.promo_code import PromoCode
from app.models.promo_redemption import PromoRedemption
from app.models.promo_validation_attempt import PromoValidationAttempt
from app.models.registration_lock import RegistrationLock
from app.models.search import Search
from app.models.seen_job import SeenJob
from app.models.site_credential import SiteCredential
from app.models.source import Source
from app.models.user import User

__all__ = [
    "ApplicationLog",
    "ApplicationProfile",
    "Base",
    "DeliveryLog",
    "NotificationTarget",
    "PasswordResetToken",
    "PendingDigest",
    "PromoCode",
    "PromoRedemption",
    "PromoValidationAttempt",
    "RegistrationLock",
    "Search",
    "SeenJob",
    "SiteCredential",
    "Source",
    "User",
]
