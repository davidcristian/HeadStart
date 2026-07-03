"""Tests for the shared apply-adapter text helpers."""

from app.appliers.text import render_cover_letter, split_name


def test_render_cover_letter_substitutes_placeholders() -> None:
    out = render_cover_letter(
        "Dear {company}, excited about {job_title} ({title}).", company="ACME", job_title="SWE"
    )
    assert out == "Dear ACME, excited about SWE (SWE)."


def test_split_name_keeps_last_name_optional() -> None:
    assert split_name("Ada Lovelace") == ("Ada", "Lovelace")
    assert split_name("Ada B Lovelace") == ("Ada", "B Lovelace")
    assert split_name("Prince") == ("Prince", "")
    assert split_name("   ") == ("", "")
