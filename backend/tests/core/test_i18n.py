"""Tests for the message catalog and locale resolution."""

from __future__ import annotations

import pytest

from app.core import i18n
from app.core.config import Settings, settings
from app.core.i18n import normalize_locale, resolve_locale, t


def test_normalize_locale_accepts_bcp47_prefixes() -> None:
    assert normalize_locale("en") == "en"
    assert normalize_locale("en-US") == "en"
    assert normalize_locale("de_DE") == "de"
    assert normalize_locale("  DE  ") == "de"
    assert normalize_locale("") is None
    assert normalize_locale("fr") is None
    assert normalize_locale(None) is None


def test_resolve_locale_falls_back_to_english_when_default_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "default_locale", "fr")
    assert resolve_locale(None) == "en"


def test_t_returns_german_digest_and_email_labels() -> None:
    assert t("digest.title_one", "de", count=1) == "1 neuer Job"
    assert t("digest.title_many", "de", count=3) == "3 neue Jobs"
    assert t("email.why_matches", "de", summary="x") == "Warum das passt: x"
    assert t("email.company", "de", company="ACME") == "Unternehmen: ACME"
    assert t("auth.reset_subject", "de") == "HeadStart-Passwort zurücksetzen"


def test_t_falls_back_to_english_catalog_when_locale_lacks_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A key present only in English still resolves under another locale."""
    monkeypatch.setitem(i18n._MESSAGES["en"], "test.only_en", "english-only")
    monkeypatch.setitem(i18n._MESSAGES["de"], "test.only_en", "")
    assert t("test.only_en", "de") == "english-only"


def test_default_locale_setting_rejects_unsupported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEFAULT_LOCALE", "fr")
    with pytest.raises(Exception, match="DEFAULT_LOCALE"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_default_locale_setting_normalizes_bcp47(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEFAULT_LOCALE", "de-DE")
    cfg = Settings(_env_file=None)  # type: ignore[call-arg]
    assert cfg.default_locale == "de"


def test_normalize_default_locale_passes_non_string() -> None:
    assert Settings._normalize_default_locale(None) is None
    assert Settings._normalize_default_locale(12) == 12
