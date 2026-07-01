"""Tests for shared Workday lookup helpers."""

from app.appliers.adapters.workday_lookup import (
    is_workday_id,
    match_lookup_item,
    normalize_lookup_text,
    parse_lookup_items,
    workday_reference,
)


def test_is_workday_id_matches_32_char_hex() -> None:
    assert is_workday_id("a1b2c3d4e5f6478990a1b2c3d4e5f678")
    assert not is_workday_id("BS")


def test_parse_lookup_items_reads_data_rows() -> None:
    items = parse_lookup_items(
        {
            "total": 2,
            "data": [
                {"id": "wid-1", "descriptor": "Bachelor of Science"},
                {"id": "wid-2", "label": "Computer Science"},
            ],
        }
    )
    assert items == [
        {"id": "wid-1", "descriptor": "Bachelor of Science"},
        {"id": "wid-2", "descriptor": "Computer Science"},
    ]


def test_match_lookup_item_prefers_exact_then_normalized_match() -> None:
    items = [
        {"id": "wid-bs", "descriptor": "BS"},
        {"id": "wid-bsc", "descriptor": "Bachelor of Science"},
    ]
    assert match_lookup_item(items, "Bachelor of Science") == items[1]
    assert match_lookup_item(items, "BS") == items[0]
    assert match_lookup_item(items, "bachelor of science") == items[1]


def test_workday_reference_uses_catalog_id_when_matched() -> None:
    match = {"id": "wid-bsc", "descriptor": "Bachelor of Science"}
    assert workday_reference("Bachelor of Science", match) == {"id": "wid-bsc"}


def test_workday_reference_falls_back_to_descriptor() -> None:
    assert workday_reference("Custom Degree", None) == {"descriptor": "Custom Degree"}


def test_normalize_lookup_text_strips_punctuation() -> None:
    assert normalize_lookup_text("B.S. Computer Science") == "bscomputerscience"
