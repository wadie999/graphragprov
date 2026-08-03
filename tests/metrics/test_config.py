"""Tests for source coverage metric configuration."""

import json

import pytest

from graphragprov.metrics.config import (
    DEFAULT_COVERAGE_METRIC_CONFIGURATION,
    CoverageMetricConfiguration,
    SentenceSegmentation,
)


def test_default_configuration_is_explicit() -> None:
    assert DEFAULT_COVERAGE_METRIC_CONFIGURATION == (
        CoverageMetricConfiguration(
            sentence_segmentation=SentenceSegmentation.REGEX_V1, statement_density_scale=1000
        )
    )


def test_configuration_is_json_serializable() -> None:
    configuration = CoverageMetricConfiguration(
        sentence_segmentation=SentenceSegmentation.REGEX_V1, statement_density_scale=500
    )

    payload = configuration.to_dict()

    assert payload == {"sentence_segmentation": "regex-v1", "statement_density_scale": 500}

    assert json.loads(json.dumps(payload, sort_keys=True)) == payload


def test_configuration_round_trip() -> None:
    configuration = CoverageMetricConfiguration(statement_density_scale=250)

    restored = CoverageMetricConfiguration.from_dict(configuration.to_dict())

    assert restored == configuration


@pytest.mark.parametrize("scale", [0, -1, -1000])
def test_statement_density_scale_must_be_positive(scale: int) -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        CoverageMetricConfiguration(statement_density_scale=scale)


def test_unknown_sentence_segmentation_is_rejected() -> None:
    with pytest.raises(ValueError):
        CoverageMetricConfiguration.from_dict(
            {"sentence_segmentation": "unknown", "statement_density_scale": 1000}
        )
