"""Complete source-coverage measurement orchestration."""

from __future__ import annotations

from graphragprov.domain.source_unit import SourceUnit
from graphragprov.extraction.result import ExtractionResult
from graphragprov.metrics.character_coverage import measure_character_coverage
from graphragprov.metrics.config import (
    DEFAULT_COVERAGE_METRIC_CONFIGURATION,
    CoverageMetricConfiguration,
)
from graphragprov.metrics.longest_uncovered import measure_longest_uncovered_text_region
from graphragprov.metrics.models import SourceCoverageMeasurements
from graphragprov.metrics.sentence_coverage import measure_sentence_coverage
from graphragprov.metrics.statement_density import measure_statement_density
from graphragprov.metrics.title_reliance import measure_title_reliance


def measure_source_coverage(
    *,
    source: SourceUnit,
    extraction: ExtractionResult,
    configuration: CoverageMetricConfiguration = (DEFAULT_COVERAGE_METRIC_CONFIGURATION),
) -> SourceCoverageMeasurements:
    """Compute every deterministic coverage metric for one source unit."""

    extraction.validate_against(source)

    return SourceCoverageMeasurements(
        unit_id=source.unit_id,
        configuration=configuration,
        character_coverage=measure_character_coverage(source=source, extraction=extraction),
        sentence_coverage=measure_sentence_coverage(
            source=source, extraction=extraction, segmentation=configuration.sentence_segmentation
        ),
        longest_uncovered_text_region=(
            measure_longest_uncovered_text_region(source=source, extraction=extraction)
        ),
        statement_density=measure_statement_density(
            source=source, extraction=extraction, configuration=configuration
        ),
        title_reliance=measure_title_reliance(source=source, extraction=extraction),
    )
