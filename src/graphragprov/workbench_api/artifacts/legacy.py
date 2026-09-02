"""Adapter for older top-level H0 artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from graphragprov.workbench_api.artifacts.helpers import extraction_run
from graphragprov.workbench_api.artifacts.types import ArtifactCase


def parse_legacy(path: Path, raw: dict[str, object]) -> ArtifactCase:
    graph = _object(raw.get("graph", {}), "graph")

    extractions = _list(graph.get("extractions", []), "graph.extractions")

    runs = tuple(
        extraction_run(cast(dict[str, Any], item)) for item in extractions if isinstance(item, dict)
    )

    provenance = raw.get("provenance")
    query = raw.get("query")

    supporting_paragraphs = _list(raw.get("supporting_paragraphs", []), "supporting_paragraphs")

    support_source_ids = _list(raw.get("support_source_ids", []), "support_source_ids")

    return ArtifactCase(
        result_path=path,
        case_id=str(raw.get("case_id", path.parents[1].name)),
        question=str(raw.get("question", "")),
        expected_answer=str(raw.get("expected_answer", "")),
        hop_count=max(1, len(supporting_paragraphs)),
        status=str(raw.get("status", "unknown")),
        failure_stage=None,
        failure_message=None,
        support_source_ids=tuple(str(item) for item in support_source_ids),
        extraction_runs=runs,
        observation=_optional_object(graph.get("observation")),
        extraction_measurements=None,
        graph_measurements=None,
        query_attempts=(cast(dict[str, object], query),) if isinstance(query, dict) else (),
        final_provenance=(
            cast(dict[str, object], provenance) if isinstance(provenance, dict) else None
        ),
        raw=raw,
    )


def _object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"artifact field {name} must be an object")

    return cast(dict[str, Any], value)


def _list(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"artifact field {name} must be a list")

    return value


def _optional_object(value: object) -> dict[str, object] | None:
    return cast(dict[str, object], value) if isinstance(value, dict) else None
