"""Executed query resources."""

from typing import Literal

from pydantic import BaseModel

from graphragprov.workbench_api.models.execution import ProvenanceAnswer


class RunError(BaseModel):
    error_type: str
    message: str


class QueryAttemptView(BaseModel):
    turn_index: int
    purpose: Literal["inspection", "candidate", "final"]
    semantic_sparql: str
    execution_sparql: str
    result: dict[str, object] | None
    rewritten_sparql: str | None
    rewritten_result: dict[str, object] | None
    provenance_status: str
    error: RunError | None = None


class QueryRun(BaseModel):
    run_id: str
    snapshot_id: str
    origin: Literal["reference", "manual", "natural_language", "interactive"]

    question: str | None
    semantic_sparql: str
    execution_sparql: str | None
    rewritten_sparql: str | None

    result: dict[str, object] | None
    rewritten_result: dict[str, object] | None

    provenance_status: str
    provenance: tuple[ProvenanceAnswer, ...]

    attempts: tuple[QueryAttemptView, ...] = ()

    answer_correct: bool | None = None
    gold_support_covered: bool | None = None

    error: RunError | None = None
    provenance_error: RunError | None = None
