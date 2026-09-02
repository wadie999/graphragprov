"""Normalized filesystem artifact types."""

from dataclasses import dataclass
from pathlib import Path

from graphragprov.extraction.run import GroundedExtractionRun


@dataclass(frozen=True, slots=True)
class ArtifactCase:
    result_path: Path
    case_id: str
    question: str
    expected_answer: str
    hop_count: int
    status: str
    failure_stage: str | None
    failure_message: str | None
    support_source_ids: tuple[str, ...]
    extraction_runs: tuple[GroundedExtractionRun, ...]
    observation: dict[str, object] | None
    extraction_measurements: dict[str, object] | None
    graph_measurements: dict[str, object] | None
    query_attempts: tuple[dict[str, object], ...]
    final_provenance: dict[str, object] | None
    raw: dict[str, object]
