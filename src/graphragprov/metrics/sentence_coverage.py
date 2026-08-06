"""Sentence coverage measurements for grounded extraction results."""

from __future__ import annotations

import re
from collections.abc import Iterable

from graphragprov.domain.source_unit import SourceUnit
from graphragprov.extraction.result import ExtractionResult
from graphragprov.extraction.span import TextSegment, TextSpan
from graphragprov.metrics.config import SentenceSegmentation
from graphragprov.metrics.intervals import CharacterInterval, merge_intervals
from graphragprov.metrics.models import SentenceCoverage, SentenceCoverageMeasurements

_SENTENCE_PATTERN = re.compile(
    r"\S(?:[^\n]*?\S)?"
    r"(?:[.!?]+(?:[\"'”’)\]]+)?(?=\s|$)|(?=\n)|(?=\s*$))"
)


def sentence_intervals(
    *, text: str, segmentation: SentenceSegmentation = SentenceSegmentation.REGEX_V1
) -> tuple[CharacterInterval, ...]:
    """Return deterministic half-open sentence intervals."""

    if segmentation is not SentenceSegmentation.REGEX_V1:
        raise ValueError(f"unsupported sentence segmentation: {segmentation}")

    return tuple(
        CharacterInterval(start=match.start(), end=match.end())
        for match in _SENTENCE_PATTERN.finditer(text)
    )


def measure_sentence_coverage(
    *,
    source: SourceUnit,
    extraction: ExtractionResult,
    segmentation: SentenceSegmentation = SentenceSegmentation.REGEX_V1,
) -> SentenceCoverageMeasurements:
    """Measure which text sentences contain grounded evidence."""

    extraction.validate_against(source)

    sentences = sentence_intervals(text=source.text, segmentation=segmentation)

    subject_spans = tuple(
        span for statement in extraction.statements for span in statement.subject.evidence
    )
    predicate_spans = tuple(
        span for statement in extraction.statements for span in statement.predicate.evidence
    )
    object_spans = tuple(
        span for statement in extraction.statements for span in statement.object.evidence
    )

    subject = _measure_spans(sentences=sentences, spans=subject_spans)
    predicate = _measure_spans(sentences=sentences, spans=predicate_spans)
    object_coverage = _measure_spans(sentences=sentences, spans=object_spans)
    entity = _measure_spans(sentences=sentences, spans=subject_spans + object_spans)
    overall = _measure_spans(
        sentences=sentences, spans=subject_spans + predicate_spans + object_spans
    )

    return SentenceCoverageMeasurements(
        overall=overall,
        subject=subject,
        predicate=predicate,
        object=object_coverage,
        entity=entity,
        relation=predicate,
    )


def _measure_spans(
    *, sentences: tuple[CharacterInterval, ...], spans: Iterable[TextSpan]
) -> SentenceCoverage:
    text_intervals = merge_intervals(
        CharacterInterval(start=span.start, end=span.end)
        for span in spans
        if span.segment is TextSegment.TEXT
    )

    covered_sentences = sum(
        1
        for sentence in sentences
        if any(_intervals_intersect(sentence, evidence) for evidence in text_intervals)
    )

    return SentenceCoverage(covered_sentences=covered_sentences, total_sentences=len(sentences))


def _intervals_intersect(first: CharacterInterval, second: CharacterInterval) -> bool:
    """Return whether two half-open intervals overlap."""

    return first.start < second.end and second.start < first.end
