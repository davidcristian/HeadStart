"""Seed example data for local development.

Idempotent: safe to run repeatedly. Creates a demo account that owns a default
ntfy target (from settings, or a random high-entropy topic when the configured
default is guessable), one example Greenhouse source, and a disabled
example search. The search is left disabled so it never sends surprise
notifications before you've set your own ntfy topic and reviewed it.

Log in to the UI with SEED_USER_EMAIL / SEED_USER_PASSWORD afterwards.

Run with: `just seed`
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.config import settings
from app.core.db import session_scope
from app.core.logging import configure_logging, get_logger
from app.core.secret_policy import generate_ntfy_topic, is_guessable_ntfy_topic
from app.core.security import hash_password
from app.models.base import utcnow
from app.models.notification_target import NotificationTarget
from app.models.search import Search
from app.models.source import Source
from app.models.user import User

logger = get_logger(__name__)


def _seed_ntfy_topic() -> str:
    """Prefer configured topic; replace guessable placeholders with a random one."""
    configured = settings.ntfy_default_topic
    if not is_guessable_ntfy_topic(configured):
        return configured.strip()
    topic = generate_ntfy_topic()
    logger.warning(
        "NTFY_DEFAULT_TOPIC is guessable (%r); seeding ntfy target with %s instead",
        configured,
        topic,
    )
    return topic


def seed() -> None:
    configure_logging()
    with session_scope() as session:
        email = settings.seed_user_email.lower()
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            # First account becomes admin (mirrors AuthService.register).
            is_first = session.scalar(select(User).limit(1)) is None
            user = User(
                email=email,
                password_hash=hash_password(settings.seed_user_password),
                is_admin=is_first,
                is_active=True,
                email_verified_at=utcnow(),
            )
            session.add(user)
            session.flush()
            logger.info("Created seed user %s (admin=%s)", email, is_first)
        elif user.email_verified_at is None:
            user.email_verified_at = utcnow()

        target = session.scalar(
            select(NotificationTarget)
            .where(NotificationTarget.user_id == user.id)
            .where(NotificationTarget.name == "Default ntfy")
        )
        if target is None:
            topic = _seed_ntfy_topic()
            target = NotificationTarget(
                user_id=user.id,
                name="Default ntfy",
                type="ntfy",
                config={
                    "server_url": settings.ntfy_default_server_url,
                    "topic": topic,
                    "priority": "default",
                },
            )
            session.add(target)
            session.flush()
            logger.info("Created default ntfy target (topic=%s)", topic)

        source = session.scalar(
            select(Source)
            .where(Source.user_id == user.id)
            .where(Source.name == "Example (Greenhouse)")
        )
        if source is None:
            source = Source(
                user_id=user.id,
                name="Example (Greenhouse)",
                adapter_key="greenhouse",
                base_url="https://boards.greenhouse.io/",
                default_config={"board_token": "example", "company": "Example"},
            )
            session.add(source)
            session.flush()
            logger.info("Created example Greenhouse source")

        existing = session.scalar(
            select(Search)
            .where(Search.user_id == user.id)
            .where(Search.name == "Example - all jobs")
        )
        if existing is None:
            session.add(
                Search(
                    user_id=user.id,
                    name="Example - all jobs",
                    source_id=source.id,
                    target_id=target.id,
                    query_url="",
                    filters={},
                    config={},
                    interval_seconds=900,
                    enabled=False,  # enable from the UI once your ntfy topic is set
                    next_run_at=utcnow(),
                )
            )
            logger.info("Created disabled example search (enable it from the UI)")

    logger.info("Seed complete.")


def main() -> None:
    seed()


if __name__ == "__main__":
    main()
