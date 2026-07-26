"""HTTP resources for configurable graph QA execution."""

from __future__ import annotations

import json
from collections.abc import Iterator
from queue import Queue
from threading import Thread
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from graphragprov.api.dependencies import (
    ExperimentRepositoryDependency,
    MusiqueQARunner,
    MusiqueQARunnerDependency,
    MusiqueQueryScope,
)
from graphragprov.api.routers._musique import (
    load_benchmark_case,
    load_experiment,
    load_experiment_case,
)
from graphragprov.benchmarks.musique import MusiqueCase, collect_musique_source_units
from graphragprov.experiments import StoredMusiqueExperiment
from graphragprov.provenance import SourceRegistry
from graphragprov.providers.deepseek import DEFAULT_DEEPSEEK_MODEL
from graphragprov.qaagent import QAAgentRunResult
from graphragprov.qaagent.trace import QAQueryAttempt

router = APIRouter(prefix="/api/v1/experiments", tags=["qa-runs"])

_STREAM_END = object()


class ExperimentCaseQARunRequest(BaseModel):
    """Configuration for one graph QA run."""

    question: str | None = Field(default=None, min_length=1)
    max_turns: int = Field(default=5, ge=1, le=20)
    query_scope: MusiqueQueryScope = "case_graphs"
    include_oracle_tuples: bool = False
    model: str = Field(default=DEFAULT_DEEPSEEK_MODEL, min_length=1)
    max_tokens: int = Field(default=16_384, ge=1)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str | None) -> str | None:
        if value is None:
            return None

        stripped = value.strip()

        if not stripped:
            raise ValueError("question must not be empty")

        return stripped


class QAFinalDecisionResponse(BaseModel):
    """Final agent decision after all executed turns."""

    status: Literal["query", "ambiguous", "unanswerable"]
    purpose: Literal["inspection", "candidate", "final"] | None
    rationale: str
    assumptions: tuple[str, ...]


class QAEvidenceSpanResponse(BaseModel):
    """One exact source-text expression."""

    segment: Literal["title", "text"]
    start: int
    end: int
    quote: str


class QAEvidenceSourceResponse(BaseModel):
    """Source unit containing a grounded occurrence."""

    unit_id: str
    title: str
    text: str


class QAEvidenceOccurrenceResponse(BaseModel):
    """One grounded tuple occurrence used by a derivation."""

    token: str
    compact_unit_id: str
    source: QAEvidenceSourceResponse
    subject_evidence: tuple[QAEvidenceSpanResponse, ...]
    predicate_evidence: tuple[QAEvidenceSpanResponse, ...]
    object_evidence: tuple[QAEvidenceSpanResponse, ...]
    triple_hash: str


class QADerivationResponse(BaseModel):
    """One product term of a provenance polynomial."""

    occurrences: tuple[QAEvidenceOccurrenceResponse, ...]


class QAAnswerResponse(BaseModel):
    """One SPARQL binding with its exact derivations."""

    binding: dict[str, object]
    polynomial: str
    derivations: tuple[QADerivationResponse, ...]


class QATurnErrorResponse(BaseModel):
    """Execution or provenance failure from one turn."""

    error_type: str | None
    message: str


class QATurnResponse(BaseModel):
    """One observable query attempt."""

    turn_index: int
    purpose: Literal["inspection", "candidate", "final"]
    semantic_sparql: str
    scoped_sparql: str
    rewritten_sparql: str | None
    original_result: dict[str, object] | None
    rewritten_result: dict[str, object] | None
    provenance_status: Literal["not_requested", "no_answers", "decoded", "unsupported", "failed"]
    answers: tuple[QAAnswerResponse, ...]
    error: QATurnErrorResponse | None


class ExperimentCaseQARunResponse(BaseModel):
    """Frontend-facing result of one graph QA run."""

    experiment_id: str
    case_id: str
    question: str
    query_scope: MusiqueQueryScope
    include_oracle_tuples: bool
    max_turns: int
    termination_reason: Literal["final_answer", "agent_decision", "budget_exhausted"]
    final_decision: QAFinalDecisionResponse
    turns: tuple[QATurnResponse, ...]


@router.post(
    "/{experiment_id}/cases/{case_id}/qa-runs",
    response_model=ExperimentCaseQARunResponse,
    summary="Run graph QA for a case",
)
def run_experiment_case_qa(
    experiment_id: str,
    case_id: str,
    request: ExperimentCaseQARunRequest,
    repository: ExperimentRepositoryDependency,
    qa_runner: MusiqueQARunnerDependency,
) -> ExperimentCaseQARunResponse:
    """Execute one complete graph QA run."""

    experiment = load_experiment(experiment_id, repository)

    materialized_case = load_experiment_case(experiment, case_id)

    benchmark_case = load_benchmark_case(experiment, materialized_case)

    resolved_question = (
        request.question if request.question is not None else benchmark_case.question
    )

    provenance_registry = _build_run_registry(
        experiment=experiment, query_scope=request.query_scope
    )

    try:
        result = qa_runner(
            case=benchmark_case,
            question=resolved_question,
            max_turns=request.max_turns,
            query_scope=request.query_scope,
            include_oracle_tuples=(request.include_oracle_tuples),
            model=request.model,
            max_tokens=request.max_tokens,
            provenance_registry=provenance_registry,
        )
    except RuntimeError as error:
        raise HTTPException(
            status_code=503, detail={"code": "qa_runtime_unavailable", "message": str(error)}
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_qa_configuration", "message": str(error)}
        ) from error

    return _to_qa_run_response(
        experiment_id=experiment.experiment_id,
        case=benchmark_case,
        question=resolved_question,
        request=request,
        result=result,
    )


@router.post(
    "/{experiment_id}/cases/{case_id}/qa-stream", summary="Stream graph QA execution for a case"
)
def stream_experiment_case_qa(
    experiment_id: str,
    case_id: str,
    request: ExperimentCaseQARunRequest,
    repository: ExperimentRepositoryDependency,
    qa_runner: MusiqueQARunnerDependency,
) -> StreamingResponse:
    """Stream one QA run as newline-delimited JSON events."""

    experiment = load_experiment(experiment_id, repository)

    materialized_case = load_experiment_case(experiment, case_id)

    benchmark_case = load_benchmark_case(experiment, materialized_case)

    resolved_question = (
        request.question if request.question is not None else benchmark_case.question
    )

    provenance_registry = _build_run_registry(
        experiment=experiment, query_scope=request.query_scope
    )

    events = _stream_qa_events(
        experiment_id=experiment.experiment_id,
        case=benchmark_case,
        question=resolved_question,
        request=request,
        qa_runner=qa_runner,
        provenance_registry=provenance_registry,
    )

    return StreamingResponse(
        events,
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _stream_qa_events(
    *,
    experiment_id: str,
    case: MusiqueCase,
    question: str,
    request: ExperimentCaseQARunRequest,
    qa_runner: MusiqueQARunner,
    provenance_registry: SourceRegistry | None,
) -> Iterator[bytes]:
    """Bridge the blocking runner to an NDJSON response."""

    queue: Queue[dict[str, object] | object] = Queue()

    def publish(event: dict[str, object]) -> None:
        queue.put({"experiment_id": experiment_id, "case_id": case.case_id, **event})

    queue.put(
        {
            "type": "run.requested",
            "experiment_id": experiment_id,
            "case_id": case.case_id,
            "question": question,
            "hop_count": case.hop_count,
            "query_scope": request.query_scope,
            "include_oracle_tuples": (request.include_oracle_tuples),
            "max_turns": request.max_turns,
            "model": request.model,
            "max_tokens": request.max_tokens,
        }
    )

    def execute() -> None:
        try:
            qa_runner(
                case=case,
                question=question,
                max_turns=request.max_turns,
                query_scope=request.query_scope,
                include_oracle_tuples=(request.include_oracle_tuples),
                model=request.model,
                max_tokens=request.max_tokens,
                provenance_registry=provenance_registry,
                event_sink=publish,
            )
        except Exception as error:
            publish(
                {
                    "type": "run.failed",
                    "error": {"error_type": type(error).__name__, "message": str(error)},
                }
            )
        finally:
            queue.put(_STREAM_END)

    worker = Thread(target=execute, name=f"qa-stream-{case.case_id}", daemon=True)
    worker.start()

    while True:
        event = queue.get()

        if event is _STREAM_END:
            break

        if not isinstance(event, dict):
            raise AssertionError("QA stream queue contained an invalid event")

        yield (json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def _build_run_registry(
    *, experiment: StoredMusiqueExperiment, query_scope: MusiqueQueryScope
) -> SourceRegistry | None:
    """Build provenance lookup for repository-wide execution."""

    if query_scope == "case_graphs":
        return None

    benchmark_cases = tuple(
        load_benchmark_case(experiment, materialized_case)
        for materialized_case in experiment.list_cases()
    )

    source_units = collect_musique_source_units(benchmark_cases)

    return SourceRegistry(source_units)


def _to_qa_run_response(
    *,
    experiment_id: str,
    case: MusiqueCase,
    question: str,
    request: ExperimentCaseQARunRequest,
    result: QAAgentRunResult,
) -> ExperimentCaseQARunResponse:
    """Project an internal QA trace into the public API."""

    return ExperimentCaseQARunResponse(
        experiment_id=experiment_id,
        case_id=case.case_id,
        question=question,
        query_scope=request.query_scope,
        include_oracle_tuples=(request.include_oracle_tuples),
        max_turns=request.max_turns,
        termination_reason=(result.termination_reason),
        final_decision=QAFinalDecisionResponse(
            status=result.decision.status,
            purpose=result.decision.purpose,
            rationale=result.decision.rationale,
            assumptions=result.decision.assumptions,
        ),
        turns=tuple(_to_qa_turn_response(attempt) for attempt in result.query_attempts),
    )


def _to_qa_turn_response(attempt: QAQueryAttempt) -> QATurnResponse:
    """Project one executed query attempt."""

    answers = tuple(
        QAAnswerResponse.model_validate(
            {
                "binding": provenance.binding,
                "polynomial": provenance.polynomial,
                "derivations": (provenance.decoded.to_dict()["derivations"]),
            }
        )
        for provenance in attempt.answer_provenances
    )

    error = (
        None
        if attempt.error_message is None
        else QATurnErrorResponse(error_type=attempt.error_type, message=attempt.error_message)
    )

    execution = attempt.execution

    return QATurnResponse(
        turn_index=attempt.turn_index,
        purpose=attempt.purpose,
        semantic_sparql=attempt.semantic_sparql,
        scoped_sparql=attempt.scoped_sparql,
        rewritten_sparql=(execution.rewritten_query if execution is not None else None),
        original_result=(execution.original_result if execution is not None else None),
        rewritten_result=(execution.rewritten_result if execution is not None else None),
        provenance_status=(attempt.provenance_status),
        answers=answers,
        error=error,
    )
