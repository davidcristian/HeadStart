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


def test_parse_lookup_items_from_bare_list() -> None:
    items = parse_lookup_items([{"wid": "w1", "name": "Alpha"}])
    assert items == [{"id": "w1", "descriptor": "Alpha"}]


def test_parse_lookup_items_returns_empty_for_scalar() -> None:
    assert parse_lookup_items("nope") == []
    assert parse_lookup_items(42) == []


def test_parse_lookup_items_skips_non_list_keys_and_missing() -> None:
    assert parse_lookup_items({"data": "not-a-list", "items": {"nope": True}}) == []


def test_parse_lookup_items_drops_unusable_rows() -> None:
    items = parse_lookup_items({"data": ["scalar", {}, {"id": "w1"}]})
    assert items == [{"id": "w1"}]


def test_parse_lookup_items_descriptor_only_row() -> None:
    items = parse_lookup_items({"data": [{"label": "Only Descriptor"}]})
    assert items == [{"descriptor": "Only Descriptor"}]


def test_match_lookup_item_returns_none_for_empty_value() -> None:
    assert match_lookup_item([{"id": "w1", "descriptor": "Alpha"}], "   ") is None


def test_match_lookup_item_by_workday_id_found_and_fallback() -> None:
    wid = "a1b2c3d4e5f6478990a1b2c3d4e5f678"
    other = "b2c3d4e5f6478990a1b2c3d4e5f67801"
    items = [{"id": wid, "descriptor": "Alpha"}]
    assert match_lookup_item(items, wid) == items[0]
    assert match_lookup_item(items, other) == {"id": other, "descriptor": other}


def test_match_lookup_item_normalized_match() -> None:
    items = [{"id": "w1", "descriptor": "Computer-Science"}]
    assert match_lookup_item(items, "computer science") == items[0]


def test_match_lookup_item_prefix_match() -> None:
    items = [{"id": "w1", "descriptor": "Bachelor of Science in Engineering"}]
    assert match_lookup_item(items, "Bachelor of Science") == items[0]


def test_match_lookup_item_substring_match() -> None:
    items = [{"id": "w1", "descriptor": "MS Data"}]
    assert match_lookup_item(items, "Advanced MS Data degree") == items[0]


def test_match_lookup_item_returns_none_without_match() -> None:
    items = [{"id": "w1", "descriptor": "Alpha"}]
    assert match_lookup_item(items, "Zeta") is None


def test_workday_reference_raises_for_empty() -> None:
    import pytest

    with pytest.raises(ValueError, match="non-empty"):
        workday_reference("   ", None)


def test_workday_reference_uses_id_for_workday_id_value() -> None:
    wid = "a1b2c3d4e5f6478990a1b2c3d4e5f678"
    assert workday_reference(wid, None) == {"id": wid}
