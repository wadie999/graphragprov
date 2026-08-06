"""Character coverage measurements for grounded extraction results."""

from __future__ import annotations

from collections.abc import Iterable

from graphragprov.domain.source_unit import SourceUnit
from graphragprov.extraction.result import ExtractionResult
from graphragprov.extraction.span import TextSegment, TextSpan
from graphragprov.metrics.intervals import CharacterInterval, covered_character_count
from graphragprov.metrics.models import (
    CharacterCoverage,
    CharacterCoverageMeasurements,
    SegmentedCharacterCoverage,
)


def measure_character_coverage(
    *, source: SourceUnit, extraction: ExtractionResult
) -> CharacterCoverageMeasurements:
    """Measure how grounded evidence occupies one source unit.

    The extraction is validated against the source before any
    measurement is computed.
    """

    extraction.validate_against(source)

    subject_spans = tuple(
        span for statement in extraction.statements for span in statement.subject.evidence
    )
    predicate_spans = tuple(
        span for statement in extraction.statements for span in statement.predicate.evidence
    )
    object_spans = tuple(
        span for statement in extraction.statements for span in statement.object.evidence
    )

    subject = _measure_spans(source=source, spans=subject_spans)
    predicate = _measure_spans(source=source, spans=predicate_spans)
    object_coverage = _measure_spans(source=source, spans=object_spans)

    entity = _measure_spans(source=source, spans=subject_spans + object_spans)
    overall = _measure_spans(source=source, spans=subject_spans + predicate_spans + object_spans)

    return CharacterCoverageMeasurements(
        overall=overall,
        subject=subject,
        predicate=predicate,
        object=object_coverage,
        entity=entity,
        relation=predicate,
    )


def _measure_spans(*, source: SourceUnit, spans: Iterable[TextSpan]) -> SegmentedCharacterCoverage:
    spans = tuple(spans)

    title_intervals = tuple(
        CharacterInterval(start=span.start, end=span.end)
        for span in spans
        if span.segment is TextSegment.TITLE
    )
    text_intervals = tuple(
        CharacterInterval(start=span.start, end=span.end)
        for span in spans
        if span.segment is TextSegment.TEXT
    )

    title = CharacterCoverage(
        covered_characters=covered_character_count(title_intervals),
        total_characters=len(source.title),
    )
    text = CharacterCoverage(
        covered_characters=covered_character_count(text_intervals),
        total_characters=len(source.text),
    )

    combined = CharacterCoverage(
        covered_characters=(title.covered_characters + text.covered_characters),
        total_characters=(title.total_characters + text.total_characters),
    )

    return SegmentedCharacterCoverage(title=title, text=text, combined=combined)
