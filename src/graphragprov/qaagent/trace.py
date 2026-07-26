"""Serializable execution traces produced by graph QA agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from graphragprov.provenance import DecodedProvenance
from graphragprov.query import ProvenanceQueryExecution

QAQueryPurpose = Literal["inspection", "candidate", "final"]

QAProvenanceStatus = Literal["not_requested", "no_answers", "decoded", "unsupported", "failed"]

_QUERY_PURPOSES: tuple[QAQueryPurpose, ...] = ("inspection", "candidate", "final")

_PROVENANCE_STATUSES: tuple[QAProvenanceStatus, ...] = (
    "not_requested",
    "no_answers",
    "decoded",
    "unsupported",
    "failed",
)


@dataclass(frozen=True, slots=True)
class QAAnswerProvenance:
    """Provenance and exact evidence for one SPARQL result binding."""

    binding: dict[str, object]
    polynomial: str
    decoded: DecodedProvenance

    def __post_init__(self) -> None:
        if not self.binding:
            raise ValueError("answer provenance binding must not be empty")

        if not self.polynomial.strip():
            raise ValueError("answer provenance polynomial must not be empty")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable representation."""

        return {
            "binding": dict(self.binding),
            "polynomial": self.polynomial,
            "decoded": self.decoded.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class QAQueryAttempt:
    """One observable SPARQL attempt made by a graph QA agent."""

    turn_index: int
    purpose: QAQueryPurpose
    semantic_sparql: str
    scoped_sparql: str
    execution: ProvenanceQueryExecution | None = None
    answer_provenances: tuple[QAAnswerProvenance, ...] = ()
    provenance_status: QAProvenanceStatus = "not_requested"
    error_type: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if self.turn_index <= 0:
            raise ValueError("query-attempt turn index must be positive")

        if self.purpose not in _QUERY_PURPOSES:
            raise ValueError("query-attempt purpose must be one of: " + ", ".join(_QUERY_PURPOSES))

        if not self.semantic_sparql.strip():
            raise ValueError("semantic SPARQL must not be empty")

        if not self.scoped_sparql.strip():
            raise ValueError("scoped SPARQL must not be empty")

        if self.provenance_status not in _PROVENANCE_STATUSES:
            raise ValueError("provenance status must be one of: " + ", ".join(_PROVENANCE_STATUSES))

        if self.answer_provenances and self.provenance_status != "decoded":
            raise ValueError("answer provenances require decoded provenance status")

        if self.provenance_status == "decoded":
            if self.execution is None:
                raise ValueError("decoded provenance requires query execution")

            if not self.answer_provenances:
                raise ValueError("decoded provenance requires answer provenances")

        if self.provenance_status == "no_answers" and self.execution is None:
            raise ValueError("no-answer provenance status requires query execution")

        if self.provenance_status == "failed" and not self.error_message:
            raise ValueError("failed provenance status requires an error message")

        if self.error_type is not None and not self.error_message:
            raise ValueError("error type requires an error message")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable trace record."""

        return {
            "turn_index": self.turn_index,
            "purpose": self.purpose,
            "semantic_sparql": self.semantic_sparql,
            "scoped_sparql": self.scoped_sparql,
            "execution": (self.execution.to_dict() if self.execution is not None else None),
            "answer_provenances": [provenance.to_dict() for provenance in self.answer_provenances],
            "provenance_status": self.provenance_status,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }
