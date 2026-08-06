"""Longest uncovered text-region measurement."""

from __future__ import annotations

from graphragprov.domain.source_unit import SourceUnit
from graphragprov.extraction.result import ExtractionResult
from graphragprov.extraction.span import TextSegment
from graphragprov.metrics.intervals import CharacterInterval, uncovered_intervals
from graphragprov.metrics.models import LongestUncoveredTextRegion


def measure_longest_uncovered_text_region(
    *, source: SourceUnit, extraction: ExtractionResult
) -> LongestUncoveredTextRegion:
    """Return the longest text region unused by grounded evidence.

    Evidence from every subject, predicate, and object is combined.
    Title evidence does not participate because title and text have
    independent character spaces.
    """

    extraction.validate_against(source)

    covered = tuple(
        CharacterInterval(start=span.start, end=span.end)
        for statement in extraction.statements
        for grounded_value in (statement.subject, statement.predicate, statement.object)
        for span in grounded_value.evidence
        if span.segment is TextSegment.TEXT
    )

    regions = uncovered_intervals(total_length=len(source.text), covered=covered)

    if not regions:
        return LongestUncoveredTextRegion.absent()

    longest = max(regions, key=lambda region: (region.length, -region.start))

    return LongestUncoveredTextRegion(
        start=longest.start,
        end=longest.end,
        length=longest.length,
        quote=source.text[longest.start : longest.end],
    )
