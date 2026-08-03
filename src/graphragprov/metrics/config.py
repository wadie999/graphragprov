"""Configuration for deterministic source coverage measurements."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class SentenceSegmentation(StrEnum):
    """Supported deterministic sentence segmentation algorithms."""

    REGEX_V1 = "regex-v1"


@dataclass(frozen=True, slots=True)
class CoverageMetricConfiguration:
    """Configuration shared by source coverage metrics."""

    sentence_segmentation: SentenceSegmentation = SentenceSegmentation.REGEX_V1
    statement_density_scale: int = 1000

    def __post_init__(self) -> None:
        if self.statement_density_scale <= 0:
            raise ValueError("statement density scale must be greater than zero")

    def to_dict(self) -> dict[str, str | int]:
        """Return a deterministic JSON-serializable representation."""

        return {
            "sentence_segmentation": self.sentence_segmentation.value,
            "statement_density_scale": self.statement_density_scale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CoverageMetricConfiguration:
        """Restore configuration from serialized data."""

        return cls(
            sentence_segmentation=SentenceSegmentation(data["sentence_segmentation"]),
            statement_density_scale=data["statement_density_scale"],
        )


DEFAULT_COVERAGE_METRIC_CONFIGURATION = CoverageMetricConfiguration()
