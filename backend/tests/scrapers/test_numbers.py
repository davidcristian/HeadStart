"""Unit tests for shared scraper count coercion (SCR-05)."""

import math

import pytest

from app.scrapers.numbers import coerce_count


@pytest.mark.parametrize(
    ("raw", "default", "expected"),
    [
        (12, 0, 12),
        (12.7, 0, 12),
        (0, 5, 0),
        (-3, 5, 5),
        ("10", 5, 5),
        (None, 5, 5),
        (True, 5, 5),
        (False, 5, 5),
        (math.inf, 7, 7),
        (-math.inf, 7, 7),
        (math.nan, 7, 7),
    ],
)
def test_coerce_count_finite_guard(raw: object, default: int, expected: int) -> None:
    """Non-finite / non-numeric totals fall back instead of raising on int()."""
    assert coerce_count(raw, default) == expected
