"""Adapter for multihop-fidelity-h0-collection-v1 artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from graphragprov.workbench_api.artifacts.helpers import extraction_run
from graphragprov.workbench_api.artifacts.types import ArtifactCase


def parse_current(path: Path, raw: dict[str, object]) -> ArtifactCase:
    outcome = _object(raw.get("outcome"), "outcome")
    status = _string(outcome.get("status"), "outcome.status")
    payload = outcome if status == "complete" else _object(outcome.get("partial", {}), "partial")
    extractions = _object(payload.get("graph_extractions", {}), "graph_extractions")
    runs = tuple(
        extraction_run(_object(item, "graph_extractions.items[]")["run"])
        for item in _list(extractions.get("items", []), "graph_extractions.items")
        if isinstance(item, dict) and isinstance(item.get("run"), dict)
    )
    return ArtifactCase(
        result_path=path,
        case_id=_string(outcome.get("case_id"), "case_id"),
        question=_string(outcome.get("question"), "question"),
        expected_answer=_string(outcome.get("expected_answer"), "expected_answer"),
        hop_count=int(outcome.get("hop_count", 0)),
        status=status,
        failure_stage=_optional_string(outcome.get("stage")),
        failure_message=_optional_string(outcome.get("error_message")),
        support_source_ids=tuple(str(x) for x in payload.get("support_source_ids", [])),
        extraction_runs=runs,
        observation=_optional_object(payload.get("observation")),
        extraction_measurements=_optional_object(payload.get("extraction_measurements")),
        graph_measurements=_optional_object(payload.get("graph_measurements")),
        query_attempts=tuple(
            cast(dict[str, object], item)
            for item in payload.get("query_attempts", [])
            if isinstance(item, dict)
        ),
        final_provenance=_optional_object(outcome.get("final_provenance")),
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


def _string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"artifact field {name} must be a string")
    return value


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_object(value: object) -> dict[str, object] | None:
    return cast(dict[str, object], value) if isinstance(value, dict) else None
