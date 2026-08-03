"""Tests for grounded-statement density measurements."""

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
from graphragprov.metrics.config import CoverageMetricConfiguration
from graphragprov.metrics.models import StatementDensity
from graphragprov.metrics.statement_density import measure_statement_density


def _source(*, title: str, text: str) -> SourceUnit:
    return SourceUnit(unit_id=source_unit_id(title=title, text=text), title=title, text=text)


def _span(*, segment: TextSegment, content: str, quote: str, occurrence: int = 0) -> TextSpan:
    start = -1

    for _ in range(occurrence + 1):
        start = content.index(quote, start + 1)

    return TextSpan(segment=segment, start=start, end=start + len(quote), quote=quote)


def _statement(
    *, text: str, subject_quote: str, predicate_quote: str, object_quote: str
) -> GroundedStatement:
    return GroundedStatement(
        subject=GroundedValue(
            value=subject_quote,
            evidence=(_span(segment=TextSegment.TEXT, content=text, quote=subject_quote),),
        ),
        predicate=GroundedValue(
            value=predicate_quote,
            evidence=(_span(segment=TextSegment.TEXT, content=text, quote=predicate_quote),),
        ),
        object=GroundedValue(
            value=object_quote,
            evidence=(_span(segment=TextSegment.TEXT, content=text, quote=object_quote),),
        ),
    )


def test_statement_density_uses_title_and_text_length() -> None:
    title = "People"
    text = "Alice knows Bob."
    source = _source(title=title, text=text)

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            _statement(
                text=text, subject_quote="Alice", predicate_quote="knows", object_quote="Bob"
            ),
        ),
    )

    measurement = measure_statement_density(source=source, extraction=extraction)

    total_characters = len(title) + len(text)

    assert measurement.statement_count == 1
    assert measurement.total_characters == total_characters
    assert measurement.scale == 1000
    assert measurement.statements_per_scale == (1000 / total_characters)


def test_density_counts_statements_not_evidence_spans() -> None:
    text = "Alice knows Bob. Carol likes Rome."
    source = _source(title="", text=text)

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            _statement(
                text=text, subject_quote="Alice", predicate_quote="knows", object_quote="Bob"
            ),
            _statement(
                text=text, subject_quote="Carol", predicate_quote="likes", object_quote="Rome"
            ),
        ),
    )

    measurement = measure_statement_density(source=source, extraction=extraction)

    assert measurement.statement_count == 2
    assert measurement.statements_per_scale == (2 * 1000 / len(text))


def test_custom_density_scale_is_used() -> None:
    text = "Alice knows Bob."
    source = _source(title="", text=text)

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            _statement(
                text=text, subject_quote="Alice", predicate_quote="knows", object_quote="Bob"
            ),
        ),
    )

    configuration = CoverageMetricConfiguration(statement_density_scale=100)

    measurement = measure_statement_density(
        source=source, extraction=extraction, configuration=configuration
    )

    assert measurement.scale == 100
    assert measurement.statements_per_scale == (100 / len(text))


def test_nonempty_source_with_no_statements_has_zero_density() -> None:
    source = _source(title="Title", text="Uncovered source text.")
    extraction = ExtractionResult(unit_id=source.unit_id, statements=())

    measurement = measure_statement_density(source=source, extraction=extraction)

    assert measurement.statement_count == 0
    assert measurement.statements_per_scale == 0.0


def test_empty_source_has_undefined_density() -> None:
    source = _source(title="", text="")
    extraction = ExtractionResult(unit_id=source.unit_id, statements=())

    measurement = measure_statement_density(source=source, extraction=extraction)

    assert measurement.statement_count == 0
    assert measurement.total_characters == 0
    assert measurement.statements_per_scale is None


def test_statement_density_is_json_serializable() -> None:
    source = _source(title="", text="Alice knows Bob.")

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            _statement(
                text=source.text, subject_quote="Alice", predicate_quote="knows", object_quote="Bob"
            ),
        ),
    )

    measurement = measure_statement_density(source=source, extraction=extraction)

    restored = json.loads(json.dumps(measurement.to_dict(), sort_keys=True))

    assert restored == {
        "scale": 1000,
        "statement_count": 1,
        "statements_per_scale": 1000 / len(source.text),
        "total_characters": len(source.text),
    }


@pytest.mark.parametrize(
    ("statement_count", "total_characters", "scale"),
    [(-1, 10, 1000), (1, -1, 1000), (1, 10, 0), (1, 10, -1), (1, 0, 1000)],
)
def test_model_rejects_invalid_values(
    statement_count: int, total_characters: int, scale: int
) -> None:
    with pytest.raises(ValueError):
        StatementDensity(
            statement_count=statement_count, total_characters=total_characters, scale=scale
        )


def test_invalid_extraction_is_rejected_before_measurement() -> None:
    source = _source(title="", text="Alice knows Bob.")
    extraction = ExtractionResult(unit_id="u_wrong", statements=())

    with pytest.raises(ValueError, match="does not match"):
        measure_statement_density(source=source, extraction=extraction)
