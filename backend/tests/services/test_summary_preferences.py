"""Tests for per-user summary preferences service."""

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import PlanLimitError, ValidationError
from app.models.user import User
from app.schemas.summary_preferences import PurposePreferencePatch, SummaryPreferencesUpdate
from app.services.summary_preferences import SummaryPreferencesService


def _pro_user(db_session: Session, email: str = "pref@example.com", **kwargs) -> User:
    user = User(email=email, password_hash="x", plan="pro", **kwargs)
    db_session.add(user)
    db_session.flush()
    return user


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


def test_pro_user_can_save_purpose_override(db_session: Session) -> None:
    user = User(
        email="purpose@example.com",
        password_hash="x",
        plan="pro",
        summary_provider="gemini",
    )
    db_session.add(user)
    db_session.flush()

    service = SummaryPreferencesService(db_session)
    result = service.update(
        user.id,
        SummaryPreferencesUpdate(
            purpose_preferences={
                "cover_letter": PurposePreferencePatch(provider="openai", model="gpt-4o"),
            }
        ),
    )

    cover = result.purpose_preferences["cover_letter"]
    assert cover.selected_provider == "openai"
    assert cover.effective_provider == "openai"
    assert cover.selected_model == "gpt-4o"
    assert cover.effective_model == "gpt-4o"

    db_session.refresh(user)
    assert user.ai_purpose_providers == {"cover_letter": "openai"}
    assert user.ai_purpose_models == {"cover_letter": "gpt-4o"}


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


def test_update_missing_user_raises(db_session: Session) -> None:
    service = SummaryPreferencesService(db_session)
    with pytest.raises(ValidationError, match="User not found"):
        service.update(999999, SummaryPreferencesUpdate(provider="openai"))


def test_update_clears_provider_and_api_key(db_session: Session) -> None:
    from app.core.crypto import encrypt

    user = _pro_user(db_session, summary_provider="openai")
    user.summary_api_key_ciphertext = encrypt("old-key")
    db_session.flush()
    service = SummaryPreferencesService(db_session)

    result = service.update(user.id, SummaryPreferencesUpdate(provider=None, api_key=""))
    assert result.selected_provider is None
    assert result.has_custom_api_key is False
    db_session.refresh(user)
    assert user.summary_provider is None
    assert user.summary_api_key_ciphertext is None


def test_update_explicit_api_key_none_is_noop(db_session: Session) -> None:
    from app.core.crypto import encrypt

    user = _pro_user(db_session, summary_provider="openai")
    user.summary_api_key_ciphertext = encrypt("keep-me")
    db_session.flush()
    service = SummaryPreferencesService(db_session)

    # api_key explicitly set to None (in fields_set) -> the "keep as-is" branch.
    result = service.update(user.id, SummaryPreferencesUpdate(api_key=None))
    assert result.has_custom_api_key is True


def test_update_rejects_invalid_provider(db_session: Session) -> None:
    user = _pro_user(db_session)
    service = SummaryPreferencesService(db_session)
    data = SummaryPreferencesUpdate.model_construct(provider="bogus")
    with pytest.raises(ValidationError, match="Unknown AI provider"):
        service.update(user.id, data)


def test_purpose_patch_unknown_key_rejected(db_session: Session) -> None:
    user = _pro_user(db_session)
    service = SummaryPreferencesService(db_session)
    with pytest.raises(ValidationError, match="Unknown AI purpose"):
        service.update(
            user.id,
            SummaryPreferencesUpdate(purpose_preferences={"nope": PurposePreferencePatch()}),
        )


def test_purpose_patch_summary_key_rejected(db_session: Session) -> None:
    user = _pro_user(db_session)
    service = SummaryPreferencesService(db_session)
    with pytest.raises(ValidationError, match="global provider field"):
        service.update(
            user.id,
            SummaryPreferencesUpdate(purpose_preferences={"summary": PurposePreferencePatch()}),
        )


def test_purpose_patch_non_overridable_rejected(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Every non-summary purpose is overridable today, so narrow the overridable
    # set to force the "cannot be overridden" guard for a valid AI purpose.
    import app.services.summary_preferences as sp

    monkeypatch.setattr(sp, "OVERRIDABLE_AI_PURPOSES", ("resume_curation",))
    user = _pro_user(db_session)
    service = SummaryPreferencesService(db_session)
    with pytest.raises(ValidationError, match="cannot be overridden"):
        service.update(
            user.id,
            SummaryPreferencesUpdate(
                purpose_preferences={"cover_letter": PurposePreferencePatch(provider="openai")}
            ),
        )


def test_purpose_patch_clears_provider_and_model(db_session: Session) -> None:
    user = _pro_user(
        db_session,
        ai_purpose_providers={"cover_letter": "openai"},
        ai_purpose_models={"cover_letter": "gpt-4o"},
    )
    service = SummaryPreferencesService(db_session)
    result = service.update(
        user.id,
        SummaryPreferencesUpdate(
            purpose_preferences={"cover_letter": PurposePreferencePatch(provider=None, model=None)}
        ),
    )
    # provider None pops, model None is a no-op (keeps existing model).
    cover = result.purpose_preferences["cover_letter"]
    assert cover.selected_provider is None
    assert cover.selected_model == "gpt-4o"


def test_purpose_patch_provider_only_leaves_model_untouched(db_session: Session) -> None:
    user = _pro_user(
        db_session,
        ai_purpose_models={"cover_letter": "existing-model"},
    )
    service = SummaryPreferencesService(db_session)
    # Only "provider" is in fields_set, so the model branch is skipped entirely.
    result = service.update(
        user.id,
        SummaryPreferencesUpdate(
            purpose_preferences={"cover_letter": PurposePreferencePatch(provider="openai")}
        ),
    )
    cover = result.purpose_preferences["cover_letter"]
    assert cover.selected_provider == "openai"
    assert cover.selected_model == "existing-model"


def test_purpose_patch_blank_model_pops(db_session: Session) -> None:
    user = _pro_user(
        db_session,
        ai_purpose_models={"cover_letter": "gpt-4o"},
    )
    service = SummaryPreferencesService(db_session)
    result = service.update(
        user.id,
        SummaryPreferencesUpdate(
            purpose_preferences={"cover_letter": PurposePreferencePatch(model="  ")}
        ),
    )
    assert result.purpose_preferences["cover_letter"].selected_model is None


def test_selected_and_effective_providers_ignore_unknown_values(db_session: Session) -> None:
    user = _pro_user(
        db_session,
        summary_provider="legacy-provider",
        ai_purpose_providers={"cover_letter": "legacy-provider"},
    )
    service = SummaryPreferencesService(db_session)
    read = service.get(user)

    # An unrecognized stored provider is surfaced as "unset" and effective falls
    # back to the heuristic default.
    assert read.selected_provider is None
    assert read.effective_provider == "heuristic"
    cover = read.purpose_preferences["cover_letter"]
    assert cover.selected_provider is None
    assert cover.effective_provider == "heuristic"
