"""Durable contract for one MuSiQue graph materialization experiment."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from graphragprov.benchmarks.musique import MusiqueCase
from graphragprov.extraction import GroundedExtractionBatchResult
from graphragprov.extraction.run import ExtractionFailureStage
from graphragprov.graphdb import GraphDBClient, GraphMaterializationSummary
from graphragprov.hashing import validate_source_unit_id

MUSIQUE_MATERIALIZATION_FORMAT = "musique-pilot-materialization-v2"

MusiqueMaterializationStatus = Literal["complete", "partial"]


@dataclass(frozen=True, slots=True)
class MusiqueMaterializationCase:
    """Immutable benchmark-case snapshot recorded by an experiment."""

    case_id: str
    hop_count: int
    question: str
    answer: str
    answer_aliases: tuple[str, ...]
    answerable: bool
    paragraph_indices: tuple[int, ...]
    gold_support_indices: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("materialization case ID must not be empty")

        if self.hop_count <= 0:
            raise ValueError("materialization case hop count must be positive")

        if not self.question.strip():
            raise ValueError("materialization case question must not be empty")

        if any(not alias.strip() for alias in self.answer_aliases):
            raise ValueError("materialization answer aliases must not contain empty values")

        _validate_ordered_indices(
            self.paragraph_indices, name="paragraph indices", allow_empty=False
        )
        _validate_ordered_indices(
            self.gold_support_indices, name="gold support indices", allow_empty=True
        )

        if not set(self.gold_support_indices).issubset(self.paragraph_indices):
            raise ValueError("gold support indices must refer to case paragraphs")

    @classmethod
    def from_case(cls, case: MusiqueCase) -> MusiqueMaterializationCase:
        """Create an experiment snapshot from one MuSiQue case."""

        return cls(
            case_id=case.case_id,
            hop_count=case.hop_count,
            question=case.question,
            answer=case.answer,
            answer_aliases=case.answer_aliases,
            answerable=case.answerable,
            paragraph_indices=tuple(paragraph.index for paragraph in case.paragraphs),
            gold_support_indices=case.gold_support_indices,
        )

    def to_dict(self) -> dict[str, object]:
        """Return the original manifest representation."""

        return {
            "case_id": self.case_id,
            "hop_count": self.hop_count,
            "question": self.question,
            "answer": self.answer,
            "answer_aliases": list(self.answer_aliases),
            "answerable": self.answerable,
            "paragraph_indices": list(self.paragraph_indices),
            "gold_support_indices": list(self.gold_support_indices),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MusiqueMaterializationCase:
        """Parse one case snapshot from manifest data."""

        _validate_fields(
            data,
            required={
                "case_id",
                "hop_count",
                "question",
                "answer",
                "answer_aliases",
                "answerable",
                "paragraph_indices",
                "gold_support_indices",
            },
            location="case",
        )

        return cls(
            case_id=_require_string(data["case_id"], "case.case_id"),
            hop_count=_require_integer(data["hop_count"], "case.hop_count"),
            question=_require_string(data["question"], "case.question"),
            answer=_require_string(data["answer"], "case.answer"),
            answer_aliases=_require_string_tuple(data["answer_aliases"], "case.answer_aliases"),
            answerable=_require_boolean(data["answerable"], "case.answerable"),
            paragraph_indices=_require_integer_tuple(
                data["paragraph_indices"], "case.paragraph_indices"
            ),
            gold_support_indices=_require_integer_tuple(
                data["gold_support_indices"], "case.gold_support_indices"
            ),
        )


@dataclass(frozen=True, slots=True)
class MusiqueMaterializationFailure:
    """One durable extraction failure recorded by an experiment."""

    unit_id: str
    title: str
    stage: ExtractionFailureStage
    error_type: str
    error_message: str
    response_available: bool
    response_path: str
    error_path: str

    def __post_init__(self) -> None:
        validate_source_unit_id(self.unit_id)

        for name, value in (
            ("title", self.title),
            ("error type", self.error_type),
            ("error message", self.error_message),
            ("response path", self.response_path),
            ("error path", self.error_path),
        ):
            if not value.strip():
                raise ValueError(f"materialization failure {name} must not be empty")

        if self.stage not in {"provider", "response_validation"}:
            raise ValueError("materialization failure stage is invalid")

    def to_dict(self) -> dict[str, object]:
        """Return the original manifest representation."""

        return {
            "unit_id": self.unit_id,
            "title": self.title,
            "stage": self.stage,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "response_available": self.response_available,
            "response_path": self.response_path,
            "error_path": self.error_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MusiqueMaterializationFailure:
        """Parse one extraction failure from manifest data."""

        _validate_fields(
            data,
            required={
                "unit_id",
                "title",
                "stage",
                "error_type",
                "error_message",
                "response_available",
                "response_path",
                "error_path",
            },
            location="failure",
        )

        raw_stage = _require_string(data["stage"], "failure.stage")

        if raw_stage not in {"provider", "response_validation"}:
            raise ValueError("failure.stage is invalid")

        return cls(
            unit_id=_require_string(data["unit_id"], "failure.unit_id"),
            title=_require_string(data["title"], "failure.title"),
            stage=cast(ExtractionFailureStage, raw_stage),
            error_type=_require_string(data["error_type"], "failure.error_type"),
            error_message=_require_string(data["error_message"], "failure.error_message"),
            response_available=_require_boolean(
                data["response_available"], "failure.response_available"
            ),
            response_path=_require_string(data["response_path"], "failure.response_path"),
            error_path=_require_string(data["error_path"], "failure.error_path"),
        )


@dataclass(frozen=True, slots=True)
class MusiqueMaterializationGraphDB:
    """GraphDB destination recorded by a materialization experiment."""

    base_url: str
    repository: str
    statements_before_run: int

    def __post_init__(self) -> None:
        if not self.base_url.strip():
            raise ValueError("materialization GraphDB base URL must not be empty")

        if not self.repository.strip():
            raise ValueError("materialization GraphDB repository must not be empty")

        if self.statements_before_run < 0:
            raise ValueError("GraphDB statement count must be non-negative")

    def to_dict(self) -> dict[str, object]:
        """Return the original manifest representation."""

        return {
            "base_url": self.base_url,
            "repository": self.repository,
            "statements_before_run": self.statements_before_run,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MusiqueMaterializationGraphDB:
        """Parse GraphDB experiment metadata."""

        _validate_fields(
            data, required={"base_url", "repository", "statements_before_run"}, location="graphdb"
        )

        return cls(
            base_url=_require_string(data["base_url"], "graphdb.base_url"),
            repository=_require_string(data["repository"], "graphdb.repository"),
            statements_before_run=_require_integer(
                data["statements_before_run"], "graphdb.statements_before_run"
            ),
        )


@dataclass(frozen=True, slots=True)
class MusiqueMaterializationManifest:
    """Complete durable result of one MuSiQue materialization experiment."""

    status: MusiqueMaterializationStatus
    created_at: datetime
    dataset_path: str
    prompt_version: str
    model: str
    max_tokens: int
    cache_root: str
    graphdb: MusiqueMaterializationGraphDB
    cases: tuple[MusiqueMaterializationCase, ...]
    paragraph_occurrence_count: int
    requested_source_count: int
    successful_extraction_count: int
    failed_extraction_count: int
    new_outcome_count: int
    reused_outcome_count: int
    source_unit_ids: tuple[str, ...]
    failures: tuple[MusiqueMaterializationFailure, ...]
    materialization: GraphMaterializationSummary

    def __post_init__(self) -> None:
        if self.status not in {"complete", "partial"}:
            raise ValueError("materialization status must be complete or partial")

        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("materialization creation time must be timezone-aware")

        for name, value in (
            ("dataset path", self.dataset_path),
            ("prompt version", self.prompt_version),
            ("model", self.model),
            ("cache root", self.cache_root),
        ):
            if not value.strip():
                raise ValueError(f"materialization {name} must not be empty")

        if self.max_tokens <= 0:
            raise ValueError("materialization max tokens must be positive")

        if not self.cases:
            raise ValueError("materialization must contain at least one case")

        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("materialization case IDs must be unique")

        if len(set(self.source_unit_ids)) != len(self.source_unit_ids):
            raise ValueError("materialization source-unit IDs must be unique")

        for unit_id in self.source_unit_ids:
            validate_source_unit_id(unit_id)

        counts = (
            self.paragraph_occurrence_count,
            self.requested_source_count,
            self.successful_extraction_count,
            self.failed_extraction_count,
            self.new_outcome_count,
            self.reused_outcome_count,
            self.materialization.source_count,
            self.materialization.statement_count,
        )

        if any(count < 0 for count in counts):
            raise ValueError("materialization counts must be non-negative")

        expected_occurrences = sum(len(case.paragraph_indices) for case in self.cases)

        if self.paragraph_occurrence_count != expected_occurrences:
            raise ValueError("paragraph occurrence count is inconsistent with cases")

        if self.requested_source_count != len(self.source_unit_ids):
            raise ValueError("requested source count is inconsistent with source IDs")

        if (
            self.successful_extraction_count + self.failed_extraction_count
            != self.requested_source_count
        ):
            raise ValueError("extraction counts are inconsistent")

        if self.failed_extraction_count != len(self.failures):
            raise ValueError("failed extraction count is inconsistent with failures")

        if self.new_outcome_count + self.reused_outcome_count != self.requested_source_count:
            raise ValueError("cache outcome counts are inconsistent")

        if self.materialization.source_count != self.successful_extraction_count:
            raise ValueError(
                "materialized source count is inconsistent with successful extractions"
            )

        if len(self.materialization.graph_iris) != self.materialization.source_count:
            raise ValueError("materialization graph count is inconsistent")

        if len(set(self.materialization.graph_iris)) != len(self.materialization.graph_iris):
            raise ValueError("materialization graph IRIs must be unique")

        failure_unit_ids = tuple(failure.unit_id for failure in self.failures)

        if len(set(failure_unit_ids)) != len(failure_unit_ids):
            raise ValueError("materialization failures must refer to unique source units")

        if not set(failure_unit_ids).issubset(self.source_unit_ids):
            raise ValueError("materialization failure refers to an unknown source unit")

        expected_status = "complete" if not self.failures else "partial"

        if self.status != expected_status:
            raise ValueError("materialization status is inconsistent with failures")

    @classmethod
    def from_execution(
        cls,
        *,
        dataset_path: Path,
        cases: tuple[MusiqueCase, ...],
        batch: GroundedExtractionBatchResult,
        materialization: GraphMaterializationSummary,
        prompt_version: str,
        model: str,
        max_tokens: int,
        cache_root: Path,
        graphdb: GraphDBClient,
        existing_statement_count: int,
        created_at: datetime | None = None,
    ) -> MusiqueMaterializationManifest:
        """Construct a durable manifest from completed application services."""

        failures = tuple(
            MusiqueMaterializationFailure(
                unit_id=failure.source.unit_id,
                title=failure.source.title,
                stage=failure.stage,
                error_type=failure.error_type,
                error_message=failure.error_message,
                response_available=failure.response is not None,
                response_path=str(cache_root / failure.source.unit_id / "response.txt"),
                error_path=str(cache_root / failure.source.unit_id / "error.json"),
            )
            for failure in batch.failures
        )

        return cls(
            status=("complete" if not failures else "partial"),
            created_at=created_at if created_at is not None else datetime.now(UTC),
            dataset_path=str(dataset_path),
            prompt_version=prompt_version,
            model=model,
            max_tokens=max_tokens,
            cache_root=str(cache_root),
            graphdb=MusiqueMaterializationGraphDB(
                base_url=graphdb.base_url,
                repository=graphdb.repository,
                statements_before_run=existing_statement_count,
            ),
            cases=tuple(MusiqueMaterializationCase.from_case(case) for case in cases),
            paragraph_occurrence_count=sum(len(case.paragraphs) for case in cases),
            requested_source_count=len(batch.items),
            successful_extraction_count=len(batch.runs),
            failed_extraction_count=len(batch.failures),
            new_outcome_count=batch.executed_count,
            reused_outcome_count=batch.reused_count,
            source_unit_ids=tuple(item.outcome.source.unit_id for item in batch.items),
            failures=failures,
            materialization=materialization,
        )

    def to_dict(self) -> dict[str, object]:
        """Return the existing v2 manifest representation."""

        return {
            "format": MUSIQUE_MATERIALIZATION_FORMAT,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "dataset_path": self.dataset_path,
            "prompt_version": self.prompt_version,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "cache_root": self.cache_root,
            "graphdb": self.graphdb.to_dict(),
            "cases": [case.to_dict() for case in self.cases],
            "paragraph_occurrence_count": self.paragraph_occurrence_count,
            "requested_source_count": self.requested_source_count,
            "successful_extraction_count": self.successful_extraction_count,
            "failed_extraction_count": self.failed_extraction_count,
            "new_outcome_count": self.new_outcome_count,
            "reused_outcome_count": self.reused_outcome_count,
            "source_unit_ids": list(self.source_unit_ids),
            "failures": [failure.to_dict() for failure in self.failures],
            "materialization": self.materialization.to_dict(),
        }

    def to_json(self) -> str:
        """Serialize the manifest deterministically."""

        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MusiqueMaterializationManifest:
        """Parse and validate one v2 materialization manifest."""

        _validate_fields(
            data,
            required={
                "format",
                "status",
                "created_at",
                "dataset_path",
                "prompt_version",
                "model",
                "max_tokens",
                "cache_root",
                "graphdb",
                "cases",
                "paragraph_occurrence_count",
                "requested_source_count",
                "successful_extraction_count",
                "failed_extraction_count",
                "new_outcome_count",
                "reused_outcome_count",
                "source_unit_ids",
                "failures",
                "materialization",
            },
            location="manifest",
        )

        manifest_format = _require_string(data["format"], "manifest.format")

        if manifest_format != MUSIQUE_MATERIALIZATION_FORMAT:
            raise ValueError(f"unsupported materialization manifest format: {manifest_format}")

        raw_status = _require_string(data["status"], "manifest.status")

        if raw_status not in {"complete", "partial"}:
            raise ValueError("manifest.status must be complete or partial")

        created_at_text = _require_string(data["created_at"], "manifest.created_at")

        try:
            created_at = datetime.fromisoformat(created_at_text)
        except ValueError as error:
            raise ValueError("manifest.created_at must be an ISO 8601 date-time") from error

        raw_cases = _require_list(data["cases"], "manifest.cases")
        raw_failures = _require_list(data["failures"], "manifest.failures")
        graphdb_data = _require_object(data["graphdb"], "manifest.graphdb")
        materialization_data = _require_object(data["materialization"], "manifest.materialization")

        _validate_fields(
            materialization_data,
            required={"source_count", "statement_count", "graph_iris"},
            location="manifest.materialization",
        )

        return cls(
            status=cast(MusiqueMaterializationStatus, raw_status),
            created_at=created_at,
            dataset_path=_require_string(data["dataset_path"], "manifest.dataset_path"),
            prompt_version=_require_string(data["prompt_version"], "manifest.prompt_version"),
            model=_require_string(data["model"], "manifest.model"),
            max_tokens=_require_integer(data["max_tokens"], "manifest.max_tokens"),
            cache_root=_require_string(data["cache_root"], "manifest.cache_root"),
            graphdb=MusiqueMaterializationGraphDB.from_dict(graphdb_data),
            cases=tuple(
                MusiqueMaterializationCase.from_dict(
                    _require_object(value, f"manifest.cases[{index}]")
                )
                for index, value in enumerate(raw_cases)
            ),
            paragraph_occurrence_count=_require_integer(
                data["paragraph_occurrence_count"], "manifest.paragraph_occurrence_count"
            ),
            requested_source_count=_require_integer(
                data["requested_source_count"], "manifest.requested_source_count"
            ),
            successful_extraction_count=_require_integer(
                data["successful_extraction_count"], "manifest.successful_extraction_count"
            ),
            failed_extraction_count=_require_integer(
                data["failed_extraction_count"], "manifest.failed_extraction_count"
            ),
            new_outcome_count=_require_integer(
                data["new_outcome_count"], "manifest.new_outcome_count"
            ),
            reused_outcome_count=_require_integer(
                data["reused_outcome_count"], "manifest.reused_outcome_count"
            ),
            source_unit_ids=_require_string_tuple(
                data["source_unit_ids"], "manifest.source_unit_ids"
            ),
            failures=tuple(
                MusiqueMaterializationFailure.from_dict(
                    _require_object(value, f"manifest.failures[{index}]")
                )
                for index, value in enumerate(raw_failures)
            ),
            materialization=GraphMaterializationSummary(
                source_count=_require_integer(
                    materialization_data["source_count"], "manifest.materialization.source_count"
                ),
                statement_count=_require_integer(
                    materialization_data["statement_count"],
                    "manifest.materialization.statement_count",
                ),
                graph_iris=_require_string_tuple(
                    materialization_data["graph_iris"], "manifest.materialization.graph_iris"
                ),
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> MusiqueMaterializationManifest:
        """Parse and validate one JSON manifest."""

        try:
            raw_data = json.loads(payload)
        except json.JSONDecodeError as error:
            raise ValueError("materialization manifest contains invalid JSON") from error

        return cls.from_dict(_require_object(raw_data, "manifest"))


def load_musique_materialization_manifest(path: Path) -> MusiqueMaterializationManifest:
    """Load and validate one materialization manifest from disk."""

    return MusiqueMaterializationManifest.from_json(path.read_text(encoding="utf-8"))


def write_musique_materialization_manifest(
    path: Path, manifest: MusiqueMaterializationManifest
) -> None:
    """Persist one validated materialization manifest."""

    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(manifest.to_json() + "\n", encoding="utf-8")


def _validate_ordered_indices(values: tuple[int, ...], *, name: str, allow_empty: bool) -> None:
    if not values and not allow_empty:
        raise ValueError(f"materialization {name} must not be empty")

    if any(value < 0 for value in values):
        raise ValueError(f"materialization {name} must be non-negative")

    if values != tuple(sorted(set(values))):
        raise ValueError(f"materialization {name} must be unique and ordered")


def _validate_fields(data: dict[str, Any], *, required: set[str], location: str) -> None:
    fields = set(data)
    missing = required - fields
    unexpected = fields - required

    if missing:
        raise ValueError(f"{location} is missing field(s): {', '.join(sorted(missing))}")

    if unexpected:
        raise ValueError(
            f"{location} contains unexpected field(s): {', '.join(sorted(unexpected))}"
        )


def _require_object(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be an object")

    return cast(dict[str, Any], value)


def _require_list(value: Any, location: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{location} must be a list")

    return value


def _require_integer(value: Any, location: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{location} must be an integer")

    return value


def _require_boolean(value: Any, location: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{location} must be a boolean")

    return value


def _require_string(value: Any, location: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{location} must be a string")

    return value


def _require_string_tuple(value: Any, location: str) -> tuple[str, ...]:
    values = _require_list(value, location)

    return tuple(_require_string(item, f"{location}[{index}]") for index, item in enumerate(values))


def _require_integer_tuple(value: Any, location: str) -> tuple[int, ...]:
    values = _require_list(value, location)

    return tuple(
        _require_integer(item, f"{location}[{index}]") for index, item in enumerate(values)
    )
