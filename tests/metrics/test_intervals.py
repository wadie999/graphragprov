"""Tests for deterministic character interval operations."""

import json

import pytest

from graphragprov.metrics.intervals import (
    CharacterInterval,
    covered_character_count,
    merge_intervals,
    uncovered_intervals,
)


def test_character_interval_uses_half_open_length() -> None:
    interval = CharacterInterval(start=3, end=8)

    assert interval.length == 5
    assert interval.to_dict() == {"start": 3, "end": 8, "length": 5}


def test_character_interval_is_json_serializable() -> None:
    interval = CharacterInterval(start=2, end=6)

    assert json.loads(json.dumps(interval.to_dict())) == {"start": 2, "end": 6, "length": 4}


@pytest.mark.parametrize(("start", "end"), [(-1, 3), (5, 4)])
def test_character_interval_rejects_invalid_bounds(start: int, end: int) -> None:
    with pytest.raises(ValueError):
        CharacterInterval(start=start, end=end)


def test_merge_intervals_merges_overlapping_spans() -> None:
    intervals = (CharacterInterval(0, 5), CharacterInterval(3, 8), CharacterInterval(7, 10))

    assert merge_intervals(intervals) == (CharacterInterval(0, 10),)


def test_merge_intervals_counts_repeated_spans_once() -> None:
    intervals = (CharacterInterval(2, 7), CharacterInterval(2, 7), CharacterInterval(2, 7))

    assert merge_intervals(intervals) == (CharacterInterval(2, 7),)

    assert covered_character_count(intervals) == 5


def test_merge_intervals_merges_adjacent_spans() -> None:
    intervals = (CharacterInterval(0, 3), CharacterInterval(3, 6), CharacterInterval(6, 9))

    assert merge_intervals(intervals) == (CharacterInterval(0, 9),)


def test_merge_intervals_is_independent_of_input_order() -> None:
    intervals = (CharacterInterval(10, 12), CharacterInterval(2, 5), CharacterInterval(4, 8))

    assert merge_intervals(intervals) == (CharacterInterval(2, 8), CharacterInterval(10, 12))


def test_merge_intervals_ignores_empty_spans() -> None:
    intervals = (CharacterInterval(0, 0), CharacterInterval(2, 5), CharacterInterval(5, 5))

    assert merge_intervals(intervals) == (CharacterInterval(2, 5),)


def test_covered_character_count_uses_interval_union() -> None:
    intervals = (CharacterInterval(0, 5), CharacterInterval(3, 8), CharacterInterval(10, 12))

    assert covered_character_count(intervals) == 10


def test_uncovered_intervals_returns_internal_and_edge_regions() -> None:
    covered = (CharacterInterval(2, 5), CharacterInterval(7, 9))

    assert uncovered_intervals(total_length=12, covered=covered) == (
        CharacterInterval(0, 2),
        CharacterInterval(5, 7),
        CharacterInterval(9, 12),
    )


def test_uncovered_intervals_returns_entire_uncovered_segment() -> None:
    assert uncovered_intervals(total_length=6, covered=()) == (CharacterInterval(0, 6),)


def test_uncovered_intervals_returns_empty_for_full_coverage() -> None:
    assert uncovered_intervals(total_length=6, covered=(CharacterInterval(0, 6),)) == ()


def test_uncovered_intervals_handles_empty_segment() -> None:
    assert uncovered_intervals(total_length=0, covered=()) == ()


def test_uncovered_intervals_rejects_out_of_bounds_coverage() -> None:
    with pytest.raises(ValueError, match="covered interval exceeds total length"):
        uncovered_intervals(total_length=5, covered=(CharacterInterval(0, 6),))
