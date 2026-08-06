"""Tests for longest uncovered text-region measurement."""

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
from graphragprov.metrics.longest_uncovered import measure_longest_uncovered_text_region
from graphragprov.metrics.models import LongestUncoveredTextRegion


def _source(*, title: str, text: str) -> SourceUnit:
    return SourceUnit(unit_id=source_unit_id(title=title, text=text), title=title, text=text)


def _span(*, text: str, quote: str, occurrence: int = 0) -> TextSpan:
    start = -1

    for _ in range(occurrence + 1):
        start = text.index(quote, start + 1)

    return TextSpan(segment=TextSegment.TEXT, start=start, end=start + len(quote), quote=quote)


def _title_span(*, title: str, quote: str) -> TextSpan:
    start = title.index(quote)

    return TextSpan(segment=TextSegment.TITLE, start=start, end=start + len(quote), quote=quote)


def _value(value: str, *spans: TextSpan) -> GroundedValue:
    return GroundedValue(value=value, evidence=spans)


def _statement(
    *, subject: tuple[TextSpan, ...], predicate: tuple[TextSpan, ...], object_: tuple[TextSpan, ...]
) -> GroundedStatement:
    return GroundedStatement(
        subject=_value("subject", *subject),
        predicate=_value("predicate", *predicate),
        object=_value("object", *object_),
    )


def test_entire_text_is_uncovered_when_extraction_is_empty() -> None:
    source = _source(title="", text="Everything is uncovered.")
    extraction = ExtractionResult(unit_id=source.unit_id, statements=())

    measurement = measure_longest_uncovered_text_region(source=source, extraction=extraction)

    assert measurement == LongestUncoveredTextRegion(
        start=0, end=len(source.text), length=len(source.text), quote=source.text
    )


def test_longest_internal_uncovered_region_is_returned() -> None:
    text = "Alice knows Bob and Carol likes Rome."
    source = _source(title="", text=text)

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            _statement(
                subject=(_span(text=text, quote="Alice"),),
                predicate=(_span(text=text, quote="knows"),),
                object_=(_span(text=text, quote="Rome"),),
            ),
        ),
    )

    measurement = measure_longest_uncovered_text_region(source=source, extraction=extraction)

    start = text.index(" Bob")
    end = text.index("Rome")

    assert measurement.start == start
    assert measurement.end == end
    assert measurement.length == end - start
    assert measurement.quote == text[start:end]


def test_overlapping_and_repeated_spans_are_merged() -> None:
    text = "abcdefghij"
    source = _source(title="", text=text)

    repeated = TextSpan(segment=TextSegment.TEXT, start=0, end=5, quote="abcde")

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            _statement(
                subject=(repeated, repeated),
                predicate=(TextSpan(segment=TextSegment.TEXT, start=3, end=8, quote="defgh"),),
                object_=(TextSpan(segment=TextSegment.TEXT, start=7, end=9, quote="hi"),),
            ),
        ),
    )

    measurement = measure_longest_uncovered_text_region(source=source, extraction=extraction)

    assert measurement == LongestUncoveredTextRegion(start=9, end=10, length=1, quote="j")


def test_earliest_region_wins_when_lengths_are_equal() -> None:
    text = "aaXXbbYYcc"
    source = _source(title="", text=text)

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            _statement(
                subject=(_span(text=text, quote="XX"),),
                predicate=(_span(text=text, quote="YY"),),
                object_=(_span(text=text, quote="XX"),),
            ),
        ),
    )

    measurement = measure_longest_uncovered_text_region(source=source, extraction=extraction)

    assert measurement == LongestUncoveredTextRegion(start=0, end=2, length=2, quote="aa")


def test_fully_covered_text_has_no_uncovered_region() -> None:
    text = "Alice knows Bob."
    source = _source(title="", text=text)

    full_span = TextSpan(segment=TextSegment.TEXT, start=0, end=len(text), quote=text)

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            _statement(subject=(full_span,), predicate=(full_span,), object_=(full_span,)),
        ),
    )

    measurement = measure_longest_uncovered_text_region(source=source, extraction=extraction)

    assert measurement == LongestUncoveredTextRegion.absent()
    assert not measurement.exists


def test_empty_text_has_no_uncovered_region() -> None:
    source = _source(title="", text="")
    extraction = ExtractionResult(unit_id=source.unit_id, statements=())

    measurement = measure_longest_uncovered_text_region(source=source, extraction=extraction)

    assert measurement == LongestUncoveredTextRegion.absent()


def test_title_evidence_does_not_cover_text() -> None:
    title = "Alice"
    text = "This text remains uncovered."
    source = _source(title=title, text=text)

    title_span = _title_span(title=title, quote="Alice")

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            _statement(subject=(title_span,), predicate=(title_span,), object_=(title_span,)),
        ),
    )

    measurement = measure_longest_uncovered_text_region(source=source, extraction=extraction)

    assert measurement.start == 0
    assert measurement.end == len(text)
    assert measurement.quote == text


def test_measurement_is_json_serializable() -> None:
    source = _source(title="", text="Uncovered text.")
    extraction = ExtractionResult(unit_id=source.unit_id, statements=())

    measurement = measure_longest_uncovered_text_region(source=source, extraction=extraction)

    restored = json.loads(json.dumps(measurement.to_dict(), sort_keys=True))

    assert restored == {
        "exists": True,
        "start": 0,
        "end": 15,
        "length": 15,
        "quote": "Uncovered text.",
    }


@pytest.mark.parametrize(
    "measurement",
    [
        LongestUncoveredTextRegion(start=None, end=None, length=0, quote=""),
        LongestUncoveredTextRegion(start=0, end=3, length=3, quote="abc"),
    ],
)
def test_valid_models_are_accepted(measurement: LongestUncoveredTextRegion) -> None:
    assert measurement.length in {0, 3}


@pytest.mark.parametrize(
    ("start", "end", "length", "quote"),
    [
        (None, 2, 0, ""),
        (None, None, 1, ""),
        (None, None, 0, "x"),
        (-1, 2, 3, "abc"),
        (3, 2, 0, ""),
        (0, 3, 2, "abc"),
        (0, 3, 3, "ab"),
    ],
)
def test_model_rejects_invalid_regions(
    start: int | None, end: int | None, length: int, quote: str
) -> None:
    with pytest.raises(ValueError):
        LongestUncoveredTextRegion(start=start, end=end, length=length, quote=quote)


def test_invalid_extraction_is_rejected_before_measurement() -> None:
    source = _source(title="", text="Some text.")
    extraction = ExtractionResult(unit_id="u_wrong", statements=())

    with pytest.raises(ValueError, match="does not match"):
        measure_longest_uncovered_text_region(source=source, extraction=extraction)
