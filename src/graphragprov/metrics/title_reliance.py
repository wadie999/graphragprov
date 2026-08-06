"""Title-reliance measurements for grounded extraction results."""

from __future__ import annotations

from graphragprov.domain.source_unit import SourceUnit
from graphragprov.extraction.grounded_value import GroundedValue
from graphragprov.extraction.result import ExtractionResult
from graphragprov.extraction.span import TextSegment
from graphragprov.metrics.models import TitleReliance, TitleRelianceMeasurements


def measure_title_reliance(
    *, source: SourceUnit, extraction: ExtractionResult
) -> TitleRelianceMeasurements:
    """Measure how many statements depend on title evidence."""

    extraction.validate_against(source)

    total_statements = len(extraction.statements)

    subject_count = sum(_uses_title(statement.subject) for statement in extraction.statements)
    predicate_count = sum(_uses_title(statement.predicate) for statement in extraction.statements)
    object_count = sum(_uses_title(statement.object) for statement in extraction.statements)

    entity_count = sum(
        _uses_title(statement.subject) or _uses_title(statement.object)
        for statement in extraction.statements
    )

    overall_count = sum(
        _uses_title(statement.subject)
        or _uses_title(statement.predicate)
        or _uses_title(statement.object)
        for statement in extraction.statements
    )

    subject = TitleReliance(
        title_reliant_statements=subject_count, total_statements=total_statements
    )
    predicate = TitleReliance(
        title_reliant_statements=predicate_count, total_statements=total_statements
    )
    object_reliance = TitleReliance(
        title_reliant_statements=object_count, total_statements=total_statements
    )
    entity = TitleReliance(title_reliant_statements=entity_count, total_statements=total_statements)
    overall = TitleReliance(
        title_reliant_statements=overall_count, total_statements=total_statements
    )

    return TitleRelianceMeasurements(
        overall=overall,
        subject=subject,
        predicate=predicate,
        object=object_reliance,
        entity=entity,
        relation=predicate,
    )


def _uses_title(value: GroundedValue) -> bool:
    """Return whether one grounded value uses title evidence."""

    return any(span.segment is TextSegment.TITLE for span in value.evidence)
