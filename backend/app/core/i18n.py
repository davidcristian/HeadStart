"""Minimal message catalog for user-facing notification and auth email copy."""

from __future__ import annotations

from typing import Literal

from app.core.config import settings

Locale = Literal["en", "de"]
SUPPORTED_LOCALES: frozenset[str] = frozenset({"en", "de"})

_MESSAGES: dict[Locale, dict[str, str]] = {
    "en": {
        "job.fallback_title": "New job",
        "digest.title_one": "{count} new job",
        "digest.title_many": "{count} new jobs",
        "digest.title_with_search": "{base} for {search_name}",
        "email.why_matches": "Why this matches: {summary}",
        "email.company": "Company: {company}",
        "email.location": "Location: {location}",
        "email.apply": "Apply: {url}",
        "auth.reset_subject": "Reset your HeadStart password",
        "auth.reset_body": (
            "You requested a password reset for your HeadStart account.\n\n"
            "Open this link to choose a new password (valid for "
            "{minutes} minutes):\n\n"
            "{url}\n\n"
            "If you did not request this, you can ignore this email."
        ),
        "auth.verify_subject": "Verify your HeadStart email",
        "auth.verify_body": (
            "Thanks for creating a HeadStart account.\n\n"
            "Open this link to verify your email address (valid for "
            "{hours} hours):\n\n"
            "{url}\n\n"
            "If you did not create this account, you can ignore this email."
        ),
        "auth.existing_subject": "Your HeadStart account",
        "auth.existing_body": (
            "Someone tried to create a HeadStart account with this email address.\n\n"
            "If that was you, sign in here:\n{login_url}\n\n"
            "Forgot your password?\n{forgot_url}\n\n"
            "If you did not try to register, you can ignore this email."
        ),
    },
    "de": {
        "job.fallback_title": "Neuer Job",
        "digest.title_one": "{count} neuer Job",
        "digest.title_many": "{count} neue Jobs",
        "digest.title_with_search": "{base} für {search_name}",
        "email.why_matches": "Warum das passt: {summary}",
        "email.company": "Unternehmen: {company}",
        "email.location": "Ort: {location}",
        "email.apply": "Bewerben: {url}",
        "auth.reset_subject": "HeadStart-Passwort zurücksetzen",
        "auth.reset_body": (
            "Sie haben eine Zurücksetzung des Passworts für Ihr HeadStart-Konto "
            "angefordert.\n\n"
            "Öffnen Sie diesen Link, um ein neues Passwort zu wählen "
            "(gültig für {minutes} Minuten):\n\n"
            "{url}\n\n"
            "Wenn Sie das nicht angefordert haben, können Sie diese E-Mail "
            "ignorieren."
        ),
        "auth.verify_subject": "HeadStart-E-Mail bestätigen",
        "auth.verify_body": (
            "Danke, dass Sie ein HeadStart-Konto erstellt haben.\n\n"
            "Öffnen Sie diesen Link, um Ihre E-Mail-Adresse zu bestätigen "
            "(gültig für {hours} Stunden):\n\n"
            "{url}\n\n"
            "Wenn Sie kein Konto erstellt haben, können Sie diese E-Mail "
            "ignorieren."
        ),
        "auth.existing_subject": "Ihr HeadStart-Konto",
        "auth.existing_body": (
            "Jemand hat versucht, mit dieser E-Mail-Adresse ein HeadStart-Konto "
            "zu erstellen.\n\n"
            "Wenn Sie das waren, melden Sie sich hier an:\n{login_url}\n\n"
            "Passwort vergessen?\n{forgot_url}\n\n"
            "Wenn Sie sich nicht registrieren wollten, können Sie diese E-Mail "
            "ignorieren."
        ),
    },
}


def normalize_locale(value: str | None) -> Locale | None:
    """Map a free-form preference to a supported locale, or None if unknown."""
    if value is None:
        return None
    key = value.strip().lower().replace("_", "-")
    if not key:
        return None
    if key == "de" or key.startswith("de-"):
        return "de"
    if key == "en" or key.startswith("en-"):
        return "en"
    return None


def resolve_locale(preferred: str | None = None) -> Locale:
    """Prefer the caller's locale, else DEFAULT_LOCALE, else English."""
    normalized = normalize_locale(preferred)
    if normalized is not None:
        return normalized
    return normalize_locale(settings.default_locale) or "en"


def t(key: str, locale: str | None = None, **kwargs: object) -> str:
    """Look up a catalog string for the resolved locale (English fallback)."""
    loc = resolve_locale(locale)
    template = _MESSAGES[loc].get(key) or _MESSAGES["en"][key]
    if kwargs:
        return template.format(**kwargs)
    return template
