"""Tests for immutable metric result models."""

import json

import pytest

from graphragprov.metrics.models import (
    CharacterCoverage,
    CharacterCoverageMeasurements,
    SegmentedCharacterCoverage,
)


def test_character_coverage_computes_ratio() -> None:
    measurement = CharacterCoverage(covered_characters=4, total_characters=10)

    assert measurement.coverage_ratio == 0.4
    assert measurement.to_dict() == {
        "covered_characters": 4,
        "total_characters": 10,
        "coverage_ratio": 0.4,
    }


def test_character_coverage_handles_empty_segment_explicitly() -> None:
    measurement = CharacterCoverage(covered_characters=0, total_characters=0)

    assert measurement.coverage_ratio is None
    assert measurement.to_dict() == {
        "covered_characters": 0,
        "total_characters": 0,
        "coverage_ratio": None,
    }


@pytest.mark.parametrize(("covered", "total"), [(-1, 4), (1, -1), (5, 4)])
def test_character_coverage_rejects_invalid_counts(covered: int, total: int) -> None:
    with pytest.raises(ValueError):
        CharacterCoverage(covered_characters=covered, total_characters=total)


def test_segmented_coverage_serializes_all_spaces() -> None:
    measurement = SegmentedCharacterCoverage(
        title=CharacterCoverage(4, 10),
        text=CharacterCoverage(15, 100),
        combined=CharacterCoverage(19, 110),
    )

    assert measurement.to_dict() == {
        "title": {"covered_characters": 4, "total_characters": 10, "coverage_ratio": 0.4},
        "text": {"covered_characters": 15, "total_characters": 100, "coverage_ratio": 0.15},
        "combined": {"covered_characters": 19, "total_characters": 110, "coverage_ratio": 19 / 110},
    }


def test_character_measurements_are_json_serializable() -> None:
    segmented = SegmentedCharacterCoverage(
        title=CharacterCoverage(2, 4),
        text=CharacterCoverage(3, 6),
        combined=CharacterCoverage(5, 10),
    )

    measurements = CharacterCoverageMeasurements(
        overall=segmented,
        subject=segmented,
        predicate=segmented,
        object=segmented,
        entity=segmented,
        relation=segmented,
    )

    serialized = json.dumps(measurements.to_dict(), ensure_ascii=False, sort_keys=True)

    restored = json.loads(serialized)

    assert restored["overall"]["combined"] == {
        "covered_characters": 5,
        "total_characters": 10,
        "coverage_ratio": 0.5,
    }

    assert tuple(restored) == ("entity", "object", "overall", "predicate", "relation", "subject")
