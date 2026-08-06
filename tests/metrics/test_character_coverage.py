"""Tests for grounded character coverage measurements."""

import json

import pytest

from graphragprov.domain import SourceUnit
from graphragprov.extraction import (
    ExtractionResult,
    GroundedStatement,
    GroundedValue,
    TextSegment,
    TextSpan,
)
from graphragprov.hashing import source_unit_id
from graphragprov.metrics.character_coverage import measure_character_coverage


def _source(*, title: str, text: str) -> SourceUnit:
    return SourceUnit(unit_id=source_unit_id(title=title, text=text), title=title, text=text)


def _value(value: str, *spans: TextSpan) -> GroundedValue:
    return GroundedValue(value=value, evidence=spans)


def test_character_coverage_is_computed_for_every_role() -> None:
    source = _source(title="Albert Einstein", text="He was born in Ulm.")

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            GroundedStatement(
                subject=_value(
                    "Albert Einstein",
                    TextSpan(segment=TextSegment.TITLE, start=0, end=15, quote="Albert Einstein"),
                    TextSpan(segment=TextSegment.TEXT, start=0, end=2, quote="He"),
                ),
                predicate=_value(
                    "born in", TextSpan(segment=TextSegment.TEXT, start=7, end=14, quote="born in")
                ),
                object=_value(
                    "Ulm", TextSpan(segment=TextSegment.TEXT, start=15, end=18, quote="Ulm")
                ),
            ),
        ),
    )

    measurements = measure_character_coverage(source=source, extraction=extraction)

    assert measurements.subject.title.covered_characters == 15
    assert measurements.subject.text.covered_characters == 2

    assert measurements.predicate.title.covered_characters == 0
    assert measurements.predicate.text.covered_characters == 7

    assert measurements.object.title.covered_characters == 0
    assert measurements.object.text.covered_characters == 3

    assert measurements.entity.title.covered_characters == 15
    assert measurements.entity.text.covered_characters == 5

    assert measurements.relation == measurements.predicate

    assert measurements.overall.title.covered_characters == 15
    assert measurements.overall.text.covered_characters == 12

    assert measurements.overall.combined.covered_characters == 27
    assert measurements.overall.combined.total_characters == 34
    assert measurements.overall.combined.coverage_ratio == 27 / 34


def test_overlapping_and_repeated_spans_are_counted_once() -> None:
    source = _source(title="", text="abcdefghij")

    repeated_subject_span = TextSpan(segment=TextSegment.TEXT, start=0, end=5, quote="abcde")

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            GroundedStatement(
                subject=_value("subject", repeated_subject_span, repeated_subject_span),
                predicate=_value(
                    "predicate", TextSpan(segment=TextSegment.TEXT, start=3, end=8, quote="defgh")
                ),
                object=_value(
                    "object", TextSpan(segment=TextSegment.TEXT, start=7, end=10, quote="hij")
                ),
            ),
        ),
    )

    measurements = measure_character_coverage(source=source, extraction=extraction)

    assert measurements.subject.text.covered_characters == 5
    assert measurements.predicate.text.covered_characters == 5
    assert measurements.object.text.covered_characters == 3

    assert measurements.entity.text.covered_characters == 8

    assert measurements.overall.text.covered_characters == 10
    assert measurements.overall.text.coverage_ratio == 1.0


def test_empty_title_is_handled_explicitly() -> None:
    source = _source(title="", text="Alice knows Bob.")

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            GroundedStatement(
                subject=_value(
                    "Alice", TextSpan(segment=TextSegment.TEXT, start=0, end=5, quote="Alice")
                ),
                predicate=_value(
                    "knows", TextSpan(segment=TextSegment.TEXT, start=6, end=11, quote="knows")
                ),
                object=_value(
                    "Bob", TextSpan(segment=TextSegment.TEXT, start=12, end=15, quote="Bob")
                ),
            ),
        ),
    )

    measurements = measure_character_coverage(source=source, extraction=extraction)

    assert measurements.overall.title.covered_characters == 0
    assert measurements.overall.title.total_characters == 0
    assert measurements.overall.title.coverage_ratio is None


def test_empty_text_is_handled_explicitly() -> None:
    source = _source(title="Only title", text="")

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            GroundedStatement(
                subject=_value(
                    "Only", TextSpan(segment=TextSegment.TITLE, start=0, end=4, quote="Only")
                ),
                predicate=_value(
                    "title", TextSpan(segment=TextSegment.TITLE, start=5, end=10, quote="title")
                ),
                object=_value(
                    "Only title",
                    TextSpan(segment=TextSegment.TITLE, start=0, end=10, quote="Only title"),
                ),
            ),
        ),
    )

    measurements = measure_character_coverage(source=source, extraction=extraction)

    assert measurements.overall.text.covered_characters == 0
    assert measurements.overall.text.total_characters == 0
    assert measurements.overall.text.coverage_ratio is None

    assert measurements.overall.title.coverage_ratio == 1.0
    assert measurements.overall.combined.coverage_ratio == 1.0


def test_empty_source_and_empty_extraction_are_supported() -> None:
    source = _source(title="", text="")
    extraction = ExtractionResult(unit_id=source.unit_id, statements=())

    measurements = measure_character_coverage(source=source, extraction=extraction)

    assert measurements.overall.title.coverage_ratio is None
    assert measurements.overall.text.coverage_ratio is None
    assert measurements.overall.combined.coverage_ratio is None
    assert measurements.overall.combined.covered_characters == 0


def test_measurements_are_json_serializable() -> None:
    source = _source(title="", text="Alice knows Bob.")

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            GroundedStatement(
                subject=_value(
                    "Alice", TextSpan(segment=TextSegment.TEXT, start=0, end=5, quote="Alice")
                ),
                predicate=_value(
                    "knows", TextSpan(segment=TextSegment.TEXT, start=6, end=11, quote="knows")
                ),
                object=_value(
                    "Bob", TextSpan(segment=TextSegment.TEXT, start=12, end=15, quote="Bob")
                ),
            ),
        ),
    )

    measurements = measure_character_coverage(source=source, extraction=extraction)

    restored = json.loads(json.dumps(measurements.to_dict(), sort_keys=True))

    assert restored["overall"]["text"]["covered_characters"] == 13
    assert restored["subject"]["text"]["covered_characters"] == 5
    assert restored["predicate"]["text"]["covered_characters"] == 5
    assert restored["object"]["text"]["covered_characters"] == 3


def test_invalid_extraction_is_rejected_before_measurement() -> None:
    source = _source(title="Albert Einstein", text="He was born in Ulm.")

    extraction = ExtractionResult(unit_id="u_wrong", statements=())

    with pytest.raises(ValueError, match="does not match"):
        measure_character_coverage(source=source, extraction=extraction)
