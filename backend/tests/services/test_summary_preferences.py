"""Tests for per-user summary preferences service."""

from sqlalchemy.orm import Session

from app.core.exceptions import PlanLimitError
from app.models.user import User
from app.schemas.summary_preferences import SummaryPreferencesUpdate
from app.services.summary_preferences import SummaryPreferencesService


def test_pro_user_can_save_provider_and_key(db_session: Session) -> None:
    user = User(email="summary@example.com", password_hash="x", plan="pro")
    db_session.add(user)
    db_session.flush()

    service = SummaryPreferencesService(db_session)
    result = service.update(
        user.id,
        SummaryPreferencesUpdate(provider="anthropic", api_key="sk-ant-test"),
    )

    assert result.selected_provider == "anthropic"
    assert result.has_custom_api_key is True
    db_session.refresh(user)
    assert user.summary_provider == "anthropic"
    assert user.summary_api_key_ciphertext is not None


def test_free_user_cannot_update_summary_preferences(db_session: Session) -> None:
    user = User(email="free@example.com", password_hash="x", plan="free")
    db_session.add(user)
    db_session.flush()

    service = SummaryPreferencesService(db_session)
    try:
        service.update(user.id, SummaryPreferencesUpdate(provider="openai"))
    except PlanLimitError as exc:
        assert exc.code == "feature_ai_summaries"
    else:
        raise AssertionError("expected PlanLimitError")
