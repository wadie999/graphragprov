"""Tests for grounded sentence coverage measurements."""

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
from graphragprov.metrics.models import SentenceCoverage
from graphragprov.metrics.sentence_coverage import measure_sentence_coverage, sentence_intervals


def _source(*, title: str, text: str) -> SourceUnit:
    return SourceUnit(unit_id=source_unit_id(title=title, text=text), title=title, text=text)


def _text_span(*, text: str, quote: str) -> TextSpan:
    start = text.index(quote)

    return TextSpan(segment=TextSegment.TEXT, start=start, end=start + len(quote), quote=quote)


def _title_span(*, title: str, quote: str) -> TextSpan:
    start = title.index(quote)

    return TextSpan(segment=TextSegment.TITLE, start=start, end=start + len(quote), quote=quote)


def _value(value: str, *spans: TextSpan) -> GroundedValue:
    return GroundedValue(value=value, evidence=spans)


def test_sentence_intervals_preserve_source_offsets() -> None:
    text = "First sentence. Second sentence!\nThird sentence without punctuation"

    intervals = sentence_intervals(text=text)

    assert [text[interval.start : interval.end] for interval in intervals] == [
        "First sentence.",
        "Second sentence!",
        "Third sentence without punctuation",
    ]


def test_sentence_intervals_ignore_empty_whitespace_regions() -> None:
    text = "   First sentence.   \n\n Second sentence   "

    intervals = sentence_intervals(text=text)

    assert [text[interval.start : interval.end] for interval in intervals] == [
        "First sentence.",
        "Second sentence",
    ]


def test_sentence_coverage_is_computed_for_every_role() -> None:
    title = "Carol"
    text = "Alice knows Bob. Carol likes Rome. Nothing is extracted."
    source = _source(title=title, text=text)

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            GroundedStatement(
                subject=_value("Alice", _text_span(text=text, quote="Alice")),
                predicate=_value("knows", _text_span(text=text, quote="knows")),
                object=_value("Bob", _text_span(text=text, quote="Bob")),
            ),
            GroundedStatement(
                subject=_value("Carol", _title_span(title=title, quote="Carol")),
                predicate=_value("likes", _text_span(text=text, quote="likes")),
                object=_value("Rome", _text_span(text=text, quote="Rome")),
            ),
        ),
    )

    measurements = measure_sentence_coverage(source=source, extraction=extraction)

    assert measurements.overall.covered_sentences == 2
    assert measurements.overall.total_sentences == 3
    assert measurements.overall.coverage_ratio == 2 / 3

    assert measurements.subject.covered_sentences == 1
    assert measurements.subject.coverage_ratio == 1 / 3

    assert measurements.predicate.covered_sentences == 2
    assert measurements.predicate.coverage_ratio == 2 / 3

    assert measurements.object.covered_sentences == 2
    assert measurements.object.coverage_ratio == 2 / 3

    assert measurements.entity.covered_sentences == 2
    assert measurements.entity.coverage_ratio == 2 / 3

    assert measurements.relation == measurements.predicate


def test_partial_sentence_evidence_covers_the_sentence() -> None:
    text = "Alice knows Bob. This sentence is uncovered."
    source = _source(title="", text=text)

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            GroundedStatement(
                subject=_value("Alice", _text_span(text=text, quote="Alice")),
                predicate=_value("knows", _text_span(text=text, quote="knows")),
                object=_value("Bob", _text_span(text=text, quote="Bob")),
            ),
        ),
    )

    measurements = measure_sentence_coverage(source=source, extraction=extraction)

    assert measurements.overall == SentenceCoverage(covered_sentences=1, total_sentences=2)


def test_repeated_spans_do_not_count_sentence_more_than_once() -> None:
    text = "Alice knows Bob. Another sentence."
    source = _source(title="", text=text)

    alice = _text_span(text=text, quote="Alice")

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            GroundedStatement(
                subject=_value("Alice", alice, alice),
                predicate=_value("knows", _text_span(text=text, quote="knows")),
                object=_value("Bob", _text_span(text=text, quote="Bob")),
            ),
        ),
    )

    measurements = measure_sentence_coverage(source=source, extraction=extraction)

    assert measurements.overall.covered_sentences == 1
    assert measurements.overall.total_sentences == 2


def test_title_only_evidence_does_not_cover_text_sentences() -> None:
    title = "Alice"
    text = "No grounded evidence appears here."
    source = _source(title=title, text=text)

    title_span = _title_span(title=title, quote="Alice")

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            GroundedStatement(
                subject=_value("Alice", title_span),
                predicate=_value("described in", title_span),
                object=_value("Alice", title_span),
            ),
        ),
    )

    measurements = measure_sentence_coverage(source=source, extraction=extraction)

    assert measurements.overall.covered_sentences == 0
    assert measurements.overall.total_sentences == 1
    assert measurements.overall.coverage_ratio == 0.0


def test_empty_text_is_handled_explicitly() -> None:
    source = _source(title="", text="")
    extraction = ExtractionResult(unit_id=source.unit_id, statements=())

    measurements = measure_sentence_coverage(source=source, extraction=extraction)

    assert measurements.overall.covered_sentences == 0
    assert measurements.overall.total_sentences == 0
    assert measurements.overall.coverage_ratio is None


def test_sentence_measurements_are_json_serializable() -> None:
    text = "Alice knows Bob."
    source = _source(title="", text=text)

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            GroundedStatement(
                subject=_value("Alice", _text_span(text=text, quote="Alice")),
                predicate=_value("knows", _text_span(text=text, quote="knows")),
                object=_value("Bob", _text_span(text=text, quote="Bob")),
            ),
        ),
    )

    measurements = measure_sentence_coverage(source=source, extraction=extraction)

    restored = json.loads(json.dumps(measurements.to_dict(), sort_keys=True))

    assert restored["overall"] == {
        "covered_sentences": 1,
        "total_sentences": 1,
        "coverage_ratio": 1.0,
    }


@pytest.mark.parametrize(("covered", "total"), [(-1, 1), (1, -1), (2, 1)])
def test_sentence_coverage_rejects_invalid_counts(covered: int, total: int) -> None:
    with pytest.raises(ValueError):
        SentenceCoverage(covered_sentences=covered, total_sentences=total)


def test_invalid_extraction_is_rejected_before_measurement() -> None:
    source = _source(title="", text="Alice knows Bob.")
    extraction = ExtractionResult(unit_id="u_wrong", statements=())

    with pytest.raises(ValueError, match="does not match"):
        measure_sentence_coverage(source=source, extraction=extraction)
