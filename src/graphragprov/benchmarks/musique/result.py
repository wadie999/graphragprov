"""Serializable result of one MuSiQue case execution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

MusiqueCaseResultStatus = Literal[
    "completed",
    "extraction_failed",
    "materialization_failed",
    "sparql_generation_failed",
    "query_failed",
    "provenance_decoding_failed",
]

_RESULT_FORMAT = "musique-case-result-v1"


@dataclass(frozen=True, slots=True)
class MusiqueCaseResult:
    """Complete durable record of one MuSiQue case execution."""

    status: MusiqueCaseResultStatus
    case_id: str
    hop_count: int
    question: str
    expected_answer: str
    answer_aliases: tuple[str, ...]
    source_unit_ids: tuple[str, ...]
    gold_support_indices: tuple[int, ...]
    extraction_failures: tuple[dict[str, object], ...] = ()
    materialization: dict[str, object] | None = None
    sparql: str | None = None
    query_execution: dict[str, object] | None = None
    provenance_polynomial: str | None = None
    decoded_provenance: dict[str, object] | None = None
    error_type: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("MuSiQue case ID must not be empty")

        if self.hop_count <= 0:
            raise ValueError("MuSiQue hop count must be positive")

        if self.status == "completed":
            required = {
                "materialization": self.materialization,
                "sparql": self.sparql,
                "query_execution": self.query_execution,
                "provenance_polynomial": (self.provenance_polynomial),
                "decoded_provenance": (self.decoded_provenance),
            }

            missing = [name for name, value in required.items() if value is None]

            if missing:
                raise ValueError("completed MuSiQue result is missing: " + ", ".join(missing))

            if self.error_type is not None or self.error_message is not None:
                raise ValueError("completed MuSiQue result must not contain an error")

        elif not self.error_message:
            raise ValueError("failed MuSiQue result must contain an error message")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable record."""

        return {
            "format": _RESULT_FORMAT,
            "status": self.status,
            "case_id": self.case_id,
            "hop_count": self.hop_count,
            "question": self.question,
            "expected_answer": self.expected_answer,
            "answer_aliases": list(self.answer_aliases),
            "source_unit_ids": list(self.source_unit_ids),
            "gold_support_indices": list(self.gold_support_indices),
            "extraction_failures": list(self.extraction_failures),
            "materialization": self.materialization,
            "sparql": self.sparql,
            "query_execution": self.query_execution,
            "provenance_polynomial": (self.provenance_polynomial),
            "decoded_provenance": (self.decoded_provenance),
            "error_type": self.error_type,
            "error_message": self.error_message,
        }

    def to_json(self) -> str:
        """Serialize the result deterministically."""

        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
