"""Tests for complete source-coverage measurement composition."""

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
from graphragprov.metrics import (
    CoverageMetricConfiguration,
    SourceCoverageMeasurements,
    measure_source_coverage,
)


def _source(*, title: str, text: str) -> SourceUnit:
    return SourceUnit(unit_id=source_unit_id(title=title, text=text), title=title, text=text)


def _span(*, segment: TextSegment, content: str, quote: str) -> TextSpan:
    start = content.index(quote)

    return TextSpan(segment=segment, start=start, end=start + len(quote), quote=quote)


def _value(value: str, *spans: TextSpan) -> GroundedValue:
    return GroundedValue(value=value, evidence=spans)


def _extraction(source: SourceUnit) -> ExtractionResult:
    return ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            GroundedStatement(
                subject=_value(
                    "Alice",
                    _span(segment=TextSegment.TITLE, content=source.title, quote="Alice"),
                    _span(segment=TextSegment.TEXT, content=source.text, quote="She"),
                ),
                predicate=_value(
                    "knows", _span(segment=TextSegment.TEXT, content=source.text, quote="knows")
                ),
                object=_value(
                    "Bob", _span(segment=TextSegment.TEXT, content=source.text, quote="Bob")
                ),
            ),
        ),
    )


def test_source_coverage_composes_every_metric() -> None:
    source = _source(title="Alice", text="She knows Bob. Another sentence.")
    extraction = _extraction(source)

    configuration = CoverageMetricConfiguration(statement_density_scale=100)

    measurements = measure_source_coverage(
        source=source, extraction=extraction, configuration=configuration
    )

    assert isinstance(measurements, SourceCoverageMeasurements)

    assert measurements.format == "source-coverage-v1"
    assert measurements.unit_id == source.unit_id
    assert measurements.configuration == configuration

    assert measurements.character_coverage.overall.title.covered_characters == 5
    assert measurements.character_coverage.overall.text.covered_characters == 11

    assert measurements.sentence_coverage.overall.covered_sentences == 1
    assert measurements.sentence_coverage.overall.total_sentences == 2
    assert measurements.sentence_coverage.overall.coverage_ratio == 0.5

    assert measurements.longest_uncovered_text_region.quote == ". Another sentence."

    assert measurements.statement_density.statement_count == 1
    assert measurements.statement_density.scale == 100
    assert measurements.statement_density.statements_per_scale == (
        100 / (len(source.title) + len(source.text))
    )

    assert measurements.title_reliance.subject.reliance_rate == 1.0
    assert measurements.title_reliance.predicate.reliance_rate == 0.0
    assert measurements.title_reliance.object.reliance_rate == 0.0
    assert measurements.title_reliance.entity.reliance_rate == 1.0
    assert measurements.title_reliance.overall.reliance_rate == 1.0


def test_source_coverage_is_deterministic() -> None:
    source = _source(title="Alice", text="She knows Bob. Another sentence.")
    extraction = _extraction(source)

    first = measure_source_coverage(source=source, extraction=extraction)
    second = measure_source_coverage(source=source, extraction=extraction)

    assert first == second
    assert first.to_dict() == second.to_dict()


def test_source_coverage_is_json_serializable() -> None:
    source = _source(title="Alice", text="She knows Bob. Another sentence.")

    measurements = measure_source_coverage(source=source, extraction=_extraction(source))

    restored = json.loads(json.dumps(measurements.to_dict(), ensure_ascii=False, sort_keys=True))

    assert restored["format"] == "source-coverage-v1"
    assert restored["unit_id"] == source.unit_id

    assert restored["configuration"] == {
        "sentence_segmentation": "regex-v1",
        "statement_density_scale": 1000,
    }

    assert restored["character_coverage"]["subject"]["title"]["covered_characters"] == 5

    assert restored["sentence_coverage"]["overall"]["coverage_ratio"] == 0.5

    assert restored["longest_uncovered_text_region"]["quote"] == ". Another sentence."

    assert restored["statement_density"]["statement_count"] == 1

    assert restored["title_reliance"]["overall"]["reliance_rate"] == 1.0


def test_empty_source_and_extraction_are_supported() -> None:
    source = _source(title="", text="")
    extraction = ExtractionResult(unit_id=source.unit_id, statements=())

    measurements = measure_source_coverage(source=source, extraction=extraction)

    assert measurements.character_coverage.overall.combined.coverage_ratio is None
    assert measurements.sentence_coverage.overall.coverage_ratio is None
    assert not measurements.longest_uncovered_text_region.exists
    assert measurements.statement_density.statements_per_scale is None
    assert measurements.title_reliance.overall.reliance_rate is None


def test_uncovered_nonempty_source_is_supported() -> None:
    source = _source(title="Title", text="Nothing was extracted.")
    extraction = ExtractionResult(unit_id=source.unit_id, statements=())

    measurements = measure_source_coverage(source=source, extraction=extraction)

    assert measurements.character_coverage.overall.combined.coverage_ratio == 0.0
    assert measurements.sentence_coverage.overall.coverage_ratio == 0.0
    assert measurements.longest_uncovered_text_region.quote == source.text
    assert measurements.statement_density.statements_per_scale == 0.0
    assert measurements.title_reliance.overall.reliance_rate is None


def test_invalid_extraction_is_rejected_before_composition() -> None:
    source = _source(title="Alice", text="She knows Bob.")
    extraction = ExtractionResult(unit_id="u_wrong", statements=())

    with pytest.raises(ValueError, match="does not match"):
        measure_source_coverage(source=source, extraction=extraction)
