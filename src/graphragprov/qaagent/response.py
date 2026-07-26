"""Structured decisions returned by graph QA agents."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal, cast

QAAgentDecisionStatus = Literal["query", "ambiguous", "unanswerable"]

QAAgentQueryPurpose = Literal["inspection", "candidate", "final"]

_DECISION_STATUSES: tuple[QAAgentDecisionStatus, ...] = ("query", "ambiguous", "unanswerable")

_QUERY_PURPOSES: tuple[QAAgentQueryPurpose, ...] = ("inspection", "candidate", "final")

_REQUIRED_FIELDS = {"status", "purpose", "sparql", "rationale", "assumptions"}


@dataclass(frozen=True, slots=True)
class QAAgentDecision:
    """Validated decision produced by a graph QA agent."""

    status: QAAgentDecisionStatus
    purpose: QAAgentQueryPurpose | None
    sparql: str | None
    rationale: str
    assumptions: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.status not in _DECISION_STATUSES:
            raise ValueError(
                "QA-agent decision status must be one of: " + ", ".join(_DECISION_STATUSES)
            )

        if not self.rationale.strip():
            raise ValueError("QA-agent decision rationale must not be empty")

        if any(not assumption.strip() for assumption in self.assumptions):
            raise ValueError("QA-agent assumptions must not contain empty values")

        if self.status == "query":
            if self.purpose is None:
                raise ValueError("query decision requires a query purpose")

            if self.purpose not in _QUERY_PURPOSES:
                raise ValueError(
                    "QA-agent query purpose must be one of: " + ", ".join(_QUERY_PURPOSES)
                )

            if self.sparql is None or not self.sparql.strip():
                raise ValueError("query decision requires non-empty SPARQL")

            return

        if self.purpose is not None:
            raise ValueError(f"{self.status} decision must not contain a query purpose")

        if self.sparql is not None:
            raise ValueError(f"{self.status} decision must not contain SPARQL")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable representation."""

        return {
            "status": self.status,
            "purpose": self.purpose,
            "sparql": self.sparql,
            "rationale": self.rationale,
            "assumptions": list(self.assumptions),
        }


def parse_qa_agent_response(payload: str) -> QAAgentDecision:
    """Parse and validate one structured QA-agent response."""

    if not payload.strip():
        raise ValueError("QA-agent response must not be empty")

    try:
        raw_data = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ValueError("QA-agent response must contain valid JSON") from error

    if not isinstance(raw_data, dict):
        raise ValueError("QA-agent response must contain a JSON object")

    data = cast(dict[str, object], raw_data)

    fields = set(data)

    missing = sorted(_REQUIRED_FIELDS - fields)
    unexpected = sorted(fields - _REQUIRED_FIELDS)

    if missing:
        raise ValueError("QA-agent response is missing fields: " + ", ".join(missing))

    if unexpected:
        raise ValueError("QA-agent response contains unexpected fields: " + ", ".join(unexpected))

    status = data["status"]

    if not isinstance(status, str):
        raise ValueError("QA-agent decision status must be a string")

    if status not in _DECISION_STATUSES:
        raise ValueError(
            "QA-agent decision status must be one of: " + ", ".join(_DECISION_STATUSES)
        )

    raw_purpose = data["purpose"]

    if raw_purpose is not None and not isinstance(raw_purpose, str):
        raise ValueError("QA-agent query purpose must be a string or null")

    purpose: QAAgentQueryPurpose | None

    if raw_purpose is None:
        purpose = None
    else:
        if raw_purpose not in _QUERY_PURPOSES:
            raise ValueError("QA-agent query purpose must be one of: " + ", ".join(_QUERY_PURPOSES))

        purpose = raw_purpose

    sparql = data["sparql"]

    if sparql is not None and not isinstance(sparql, str):
        raise ValueError("QA-agent SPARQL must be a string or null")

    rationale = data["rationale"]

    if not isinstance(rationale, str):
        raise ValueError("QA-agent rationale must be a string")

    raw_assumptions = data["assumptions"]

    if not isinstance(raw_assumptions, list):
        raise ValueError("QA-agent assumptions must be a list")

    assumptions: list[str] = []

    for index, assumption in enumerate(raw_assumptions):
        if not isinstance(assumption, str):
            raise ValueError(f"QA-agent assumption {index} must be a string")

        assumptions.append(assumption)

    return QAAgentDecision(
        status=status,
        purpose=purpose,
        sparql=sparql,
        rationale=rationale,
        assumptions=tuple(assumptions),
    )
