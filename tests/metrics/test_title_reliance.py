"""Tests for title-reliance measurements."""

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
from graphragprov.metrics.models import TitleReliance
from graphragprov.metrics.title_reliance import measure_title_reliance


def _source(*, title: str, text: str) -> SourceUnit:
    return SourceUnit(unit_id=source_unit_id(title=title, text=text), title=title, text=text)


def _span(*, segment: TextSegment, content: str, quote: str, occurrence: int = 0) -> TextSpan:
    start = -1

    for _ in range(occurrence + 1):
        start = content.index(quote, start + 1)

    return TextSpan(segment=segment, start=start, end=start + len(quote), quote=quote)


def _value(value: str, *spans: TextSpan) -> GroundedValue:
    return GroundedValue(value=value, evidence=spans)


def test_title_reliance_is_computed_for_every_role() -> None:
    title = "Alice knows Bob"
    text = "Alice knows Bob. Carol likes Rome. David visits Paris."
    source = _source(title=title, text=text)

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            GroundedStatement(
                subject=_value(
                    "Alice", _span(segment=TextSegment.TITLE, content=title, quote="Alice")
                ),
                predicate=_value(
                    "knows", _span(segment=TextSegment.TEXT, content=text, quote="knows")
                ),
                object=_value("Bob", _span(segment=TextSegment.TEXT, content=text, quote="Bob")),
            ),
            GroundedStatement(
                subject=_value(
                    "Carol", _span(segment=TextSegment.TEXT, content=text, quote="Carol")
                ),
                predicate=_value(
                    "likes", _span(segment=TextSegment.TITLE, content=title, quote="knows")
                ),
                object=_value("Rome", _span(segment=TextSegment.TEXT, content=text, quote="Rome")),
            ),
            GroundedStatement(
                subject=_value(
                    "David", _span(segment=TextSegment.TEXT, content=text, quote="David")
                ),
                predicate=_value(
                    "visits", _span(segment=TextSegment.TEXT, content=text, quote="visits")
                ),
                object=_value(
                    "Paris", _span(segment=TextSegment.TITLE, content=title, quote="Bob")
                ),
            ),
        ),
    )

    measurements = measure_title_reliance(source=source, extraction=extraction)

    assert measurements.subject == TitleReliance(title_reliant_statements=1, total_statements=3)
    assert measurements.predicate == TitleReliance(title_reliant_statements=1, total_statements=3)
    assert measurements.object == TitleReliance(title_reliant_statements=1, total_statements=3)

    assert measurements.entity.title_reliant_statements == 2
    assert measurements.entity.reliance_rate == 2 / 3

    assert measurements.relation == measurements.predicate

    assert measurements.overall.title_reliant_statements == 3
    assert measurements.overall.reliance_rate == 1.0


def test_multiple_title_spans_count_one_statement_once() -> None:
    title = "Alice Bob"
    text = "Alice knows Bob."
    source = _source(title=title, text=text)

    alice_title = _span(segment=TextSegment.TITLE, content=title, quote="Alice")
    bob_title = _span(segment=TextSegment.TITLE, content=title, quote="Bob")

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            GroundedStatement(
                subject=_value("Alice", alice_title, alice_title, bob_title),
                predicate=_value(
                    "knows", _span(segment=TextSegment.TEXT, content=text, quote="knows")
                ),
                object=_value("Bob", _span(segment=TextSegment.TEXT, content=text, quote="Bob")),
            ),
        ),
    )

    measurements = measure_title_reliance(source=source, extraction=extraction)

    assert measurements.subject.title_reliant_statements == 1
    assert measurements.subject.total_statements == 1
    assert measurements.subject.reliance_rate == 1.0


def test_statement_using_title_in_multiple_roles_counts_once_overall() -> None:
    title = "Alice knows Bob"
    source = _source(title=title, text="")

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            GroundedStatement(
                subject=_value(
                    "Alice", _span(segment=TextSegment.TITLE, content=title, quote="Alice")
                ),
                predicate=_value(
                    "knows", _span(segment=TextSegment.TITLE, content=title, quote="knows")
                ),
                object=_value("Bob", _span(segment=TextSegment.TITLE, content=title, quote="Bob")),
            ),
        ),
    )

    measurements = measure_title_reliance(source=source, extraction=extraction)

    assert measurements.overall.title_reliant_statements == 1
    assert measurements.overall.total_statements == 1


def test_text_only_extraction_has_zero_title_reliance() -> None:
    text = "Alice knows Bob."
    source = _source(title="", text=text)

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            GroundedStatement(
                subject=_value(
                    "Alice", _span(segment=TextSegment.TEXT, content=text, quote="Alice")
                ),
                predicate=_value(
                    "knows", _span(segment=TextSegment.TEXT, content=text, quote="knows")
                ),
                object=_value("Bob", _span(segment=TextSegment.TEXT, content=text, quote="Bob")),
            ),
        ),
    )

    measurements = measure_title_reliance(source=source, extraction=extraction)

    assert measurements.overall.title_reliant_statements == 0
    assert measurements.overall.reliance_rate == 0.0
    assert measurements.subject.reliance_rate == 0.0
    assert measurements.predicate.reliance_rate == 0.0
    assert measurements.object.reliance_rate == 0.0


def test_empty_extraction_has_undefined_title_reliance() -> None:
    source = _source(title="Title", text="Some text.")
    extraction = ExtractionResult(unit_id=source.unit_id, statements=())

    measurements = measure_title_reliance(source=source, extraction=extraction)

    assert measurements.overall.title_reliant_statements == 0
    assert measurements.overall.total_statements == 0
    assert measurements.overall.reliance_rate is None

    assert measurements.subject.reliance_rate is None
    assert measurements.predicate.reliance_rate is None
    assert measurements.object.reliance_rate is None


def test_title_reliance_is_json_serializable() -> None:
    title = "Alice"
    source = _source(title=title, text="")

    title_span = _span(segment=TextSegment.TITLE, content=title, quote="Alice")

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            GroundedStatement(
                subject=_value("Alice", title_span),
                predicate=_value("describes", title_span),
                object=_value("Alice", title_span),
            ),
        ),
    )

    measurements = measure_title_reliance(source=source, extraction=extraction)

    restored = json.loads(json.dumps(measurements.to_dict(), sort_keys=True))

    assert restored["overall"] == {
        "reliance_rate": 1.0,
        "title_reliant_statements": 1,
        "total_statements": 1,
    }


@pytest.mark.parametrize(("title_reliant", "total"), [(-1, 1), (1, -1), (2, 1)])
def test_model_rejects_invalid_counts(title_reliant: int, total: int) -> None:
    with pytest.raises(ValueError):
        TitleReliance(title_reliant_statements=title_reliant, total_statements=total)


def test_invalid_extraction_is_rejected_before_measurement() -> None:
    source = _source(title="", text="Alice knows Bob.")
    extraction = ExtractionResult(unit_id="u_wrong", statements=())

    with pytest.raises(ValueError, match="does not match"):
        measure_title_reliance(source=source, extraction=extraction)
