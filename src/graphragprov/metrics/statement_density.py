"""Statement-density measurement for grounded extraction results."""

from __future__ import annotations

from graphragprov.domain.source_unit import SourceUnit
from graphragprov.extraction.result import ExtractionResult
from graphragprov.metrics.config import (
    DEFAULT_COVERAGE_METRIC_CONFIGURATION,
    CoverageMetricConfiguration,
)
from graphragprov.metrics.models import StatementDensity


def measure_statement_density(
    *,
    source: SourceUnit,
    extraction: ExtractionResult,
    configuration: CoverageMetricConfiguration = (DEFAULT_COVERAGE_METRIC_CONFIGURATION),
) -> StatementDensity:
    """Measure accepted statements per configured source-character scale."""

    extraction.validate_against(source)

    return StatementDensity(
        statement_count=len(extraction.statements),
        total_characters=len(source.title) + len(source.text),
        scale=configuration.statement_density_scale,
    )
