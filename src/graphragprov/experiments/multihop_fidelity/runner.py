"""Execution of one multi-hop fidelity H0 case."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from graphragprov.benchmarks.musique import MusiqueCase, MusiqueSourceUnit
from graphragprov.experiments.multihop_fidelity.config import ArtifactOrigin, ExperimentConfig
from graphragprov.experiments.multihop_fidelity.graph import (
    ReferenceGraphExtractionFailure,
    ReferenceGraphExtractionResult,
    ReferenceGraphProgressSink,
    construct_reference_extractions,
    reference_supporting_paragraphs,
)
from graphragprov.experiments.multihop_fidelity.measurements import (
    FrozenGraphMeasurements,
    ReferenceExtractionMeasurements,
    measure_frozen_graph,
    measure_reference_extractions,
)
from graphragprov.experiments.multihop_fidelity.query import (
    ReferenceQueryPlan,
    ReferenceQueryValidationError,
    answer_terms,
    compile_reference_query,
    display_answer_term,
    generate_reference_query,
    validation_feedback,
)
from graphragprov.experiments.multihop_fidelity.telemetry import (
    ExperimentTelemetry,
    ExperimentTelemetryRecorder,
)
from graphragprov.extraction.run import (
    GenerateResponse,
    GroundedExtractionCorrection,
    GroundedExtractionRun,
)
from graphragprov.graphdb import (
    GraphDBClient,
    GraphMaterializationSummary,
    materialize_grounded_extractions,
)
from graphragprov.npcs import NPCSClient
from graphragprov.provenance import SourceRegistry
from graphragprov.qaagent import (
    QAAgentObservation,
    QAQueryAttempt,
    execute_qa_query_attempt,
    observe_semantic_triples,
)
from graphragprov.rdf.terms import unit_graph_iri

H0ProgressSink: TypeAlias = ReferenceGraphProgressSink

H0FailureStage = Literal[
    "graph_extraction",
    "graph_measurement",
    "graph_clear",
    "graph_materialization",
    "graph_observation",
    "query_generation",
    "query_execution",
    "provenance",
]


@dataclass(frozen=True, slots=True)
class H0QueryAttemptRecord:
    """One complete reference-query attempt."""

    attempt_index: int
    prompt: str
    response: str
    plan: ReferenceQueryPlan | None = None
    execution_sparql: str | None = None
    original_result: dict[str, object] | None = None
    observed_answers: tuple[str, ...] = ()
    answer_correct: bool | None = None
    validation_error: str | None = None
    provenance: QAQueryAttempt | None = None
    gold_support_covered: bool | None = None
    feedback: str | None = None

    def __post_init__(self) -> None:
        if self.attempt_index < 1:
            raise ValueError("query attempt index must be positive")

        if not self.prompt.strip():
            raise ValueError("query attempt prompt must not be empty")

        if not self.response.strip():
            raise ValueError("query attempt response must not be empty")

        if self.validation_error is not None and self.plan is not None:
            raise ValueError("invalid query attempt must not contain a validated plan")

        if self.answer_correct is not None and self.original_result is None:
            raise ValueError("answer correctness requires an original GraphDB result")

        if self.gold_support_covered is not None and self.provenance is None:
            raise ValueError("gold support coverage requires a provenance attempt")

    def to_dict(self) -> dict[str, object]:
        return {
            "attempt_index": (self.attempt_index),
            "prompt": self.prompt,
            "response": self.response,
            "plan": (self.plan.to_dict() if self.plan is not None else None),
            "execution_sparql": (self.execution_sparql),
            "original_result": (self.original_result),
            "observed_answers": list(self.observed_answers),
            "answer_correct": (self.answer_correct),
            "validation_error": (self.validation_error),
            "provenance": (self.provenance.to_dict() if self.provenance is not None else None),
            "gold_support_covered": (self.gold_support_covered),
            "feedback": self.feedback,
        }


@dataclass(frozen=True, slots=True)
class H0CaseResult:
    """Completed observable H0 collection for one MuSiQue case."""

    case_id: str
    question: str
    expected_answer: str
    hop_count: int
    configuration: ExperimentConfig
    support_source_ids: tuple[str, ...]
    graph_extractions: ReferenceGraphExtractionResult
    extraction_measurements: ReferenceExtractionMeasurements
    materialization: GraphMaterializationSummary
    observation: QAAgentObservation
    graph_measurements: FrozenGraphMeasurements
    query_attempts: tuple[H0QueryAttemptRecord, ...]
    final_provenance: QAQueryAttempt
    telemetry: ExperimentTelemetry

    def __post_init__(self) -> None:
        if self.hop_count < 1:
            raise ValueError("H0 result hop count must be positive")

        if not self.support_source_ids:
            raise ValueError("H0 result must contain supporting source IDs")

        if not self.query_attempts:
            raise ValueError("H0 result must contain at least one query attempt")

        final_attempt = self.query_attempts[-1]

        if final_attempt.original_result is None:
            raise ValueError("completed H0 collection requires an executed query")

        if final_attempt.provenance is None:
            raise ValueError("completed H0 collection requires a provenance attempt")

    def to_dict(self) -> dict[str, object]:
        return {
            "status": "complete",
            "case_id": self.case_id,
            "question": self.question,
            "expected_answer": (self.expected_answer),
            "hop_count": self.hop_count,
            "configuration": (_configuration_to_dict(self.configuration)),
            "support_source_ids": list(self.support_source_ids),
            "graph_extractions": (_reference_extractions_to_dict(self.graph_extractions)),
            "extraction_measurements": (self.extraction_measurements.to_dict()),
            "materialization": (self.materialization.to_dict()),
            "observation": (self.observation.to_dict()),
            "graph_measurements": (self.graph_measurements.to_dict()),
            "query_attempts": [attempt.to_dict() for attempt in self.query_attempts],
            "final_provenance": (self.final_provenance.to_dict()),
            "telemetry": (self.telemetry.to_dict()),
        }


@dataclass(frozen=True, slots=True)
class H0CaseFailure:
    """Inspectable operational failure while collecting one H0 case."""

    case_id: str
    question: str
    expected_answer: str
    hop_count: int
    configuration: ExperimentConfig
    stage: H0FailureStage
    error_type: str
    error_message: str
    telemetry: ExperimentTelemetry
    partial: dict[str, object]

    def __post_init__(self) -> None:
        if self.hop_count < 1:
            raise ValueError("H0 failure hop count must be positive")

        if not self.error_type.strip():
            raise ValueError("H0 failure error type must not be empty")

        if not self.error_message.strip():
            raise ValueError("H0 failure error message must not be empty")

    def to_dict(self) -> dict[str, object]:
        return {
            "status": "operational_failure",
            "case_id": self.case_id,
            "question": self.question,
            "expected_answer": (self.expected_answer),
            "hop_count": self.hop_count,
            "configuration": (_configuration_to_dict(self.configuration)),
            "stage": self.stage,
            "error_type": (self.error_type),
            "error_message": (self.error_message),
            "telemetry": (self.telemetry.to_dict()),
            "partial": self.partial,
        }


H0CaseOutcome: TypeAlias = H0CaseResult | H0CaseFailure


def run_h0_case(
    *,
    case: MusiqueCase,
    sources: tuple[MusiqueSourceUnit, ...],
    configuration: ExperimentConfig,
    graph_generate_response: GenerateResponse,
    query_generate_response: GenerateResponse,
    graphdb: GraphDBClient,
    npcs: NPCSClient,
    telemetry: ExperimentTelemetryRecorder,
    progress_sink: (H0ProgressSink | None) = None,
) -> H0CaseOutcome:
    """Run one complete H0 reference case."""

    if configuration.graph_origin is not ArtifactOrigin.REFERENCE:
        raise ValueError("H0 requires graph_origin=reference")

    if configuration.query_origin is not ArtifactOrigin.REFERENCE:
        raise ValueError("H0 requires query_origin=reference")

    if not case.answerable:
        raise ValueError("H0 requires an answerable MuSiQue case")

    support_paragraphs = reference_supporting_paragraphs(case)

    source_by_id = {source.unit_id: source for source in sources}

    try:
        support_sources = tuple(source_by_id[paragraph.unit_id] for paragraph in support_paragraphs)
    except KeyError as error:
        return _failure(
            case=case,
            configuration=configuration,
            stage="graph_extraction",
            error_type="ValueError",
            error_message=(
                "one or more supporting sources are missing from the supplied source collection"
            ),
            telemetry=telemetry,
            partial={"missing_source_unit_id": (str(error.args[0]))},
        )

    support_source_ids = tuple(source.unit_id for source in support_sources)

    _emit_progress(
        progress_sink,
        "graph.extraction.started",
        {"source_count": len(support_sources), "support_source_ids": (support_source_ids)},
    )

    with telemetry.measure_stage("graph.reference.extraction"):
        graph_outcome = construct_reference_extractions(
            case=case,
            sources=sources,
            generate_response=(graph_generate_response),
            max_attempts=(configuration.max_source_attempts),
            progress_sink=(progress_sink),
        )

    if isinstance(graph_outcome, ReferenceGraphExtractionFailure):
        return _failure(
            case=case,
            configuration=configuration,
            stage="graph_extraction",
            error_type=(graph_outcome.failure.error_type),
            error_message=(graph_outcome.failure.error_message),
            telemetry=telemetry,
            partial={
                "support_source_ids": list(support_source_ids),
                "graph_extraction": (_reference_failure_to_dict(graph_outcome)),
            },
        )

    try:
        with telemetry.measure_stage("graph.reference.measurements"):
            extraction_measurements = measure_reference_extractions(graph_outcome)
    except Exception as error:
        return _failure(
            case=case,
            configuration=configuration,
            stage="graph_measurement",
            error_type=(type(error).__name__),
            error_message=str(error),
            telemetry=telemetry,
            partial={
                "support_source_ids": list(support_source_ids),
                "graph_extractions": (_reference_extractions_to_dict(graph_outcome)),
            },
        )

    _emit_progress(
        progress_sink, "graph.extraction.measured", {"measurements": (extraction_measurements)}
    )

    try:
        with telemetry.measure_stage("graph.clear_support"):
            for source_id in support_source_ids:
                graphdb.update(f"CLEAR SILENT GRAPH {unit_graph_iri(source_id).n3()}")
    except Exception as error:
        return _failure(
            case=case,
            configuration=configuration,
            stage="graph_clear",
            error_type=(type(error).__name__),
            error_message=str(error),
            telemetry=telemetry,
            partial={
                "support_source_ids": list(support_source_ids),
                "graph_extractions": (_reference_extractions_to_dict(graph_outcome)),
                "extraction_measurements": (extraction_measurements.to_dict()),
            },
        )

    _emit_progress(
        progress_sink, "graph.materialization.started", {"source_count": len(support_source_ids)}
    )

    try:
        with telemetry.measure_stage("graph.materialization"):
            materialization = materialize_grounded_extractions(graph_outcome.runs, graphdb=graphdb)
    except Exception as error:
        return _failure(
            case=case,
            configuration=configuration,
            stage="graph_materialization",
            error_type=(type(error).__name__),
            error_message=str(error),
            telemetry=telemetry,
            partial={
                "support_source_ids": list(support_source_ids),
                "graph_extractions": (_reference_extractions_to_dict(graph_outcome)),
                "extraction_measurements": (extraction_measurements.to_dict()),
            },
        )

    _emit_progress(
        progress_sink, "graph.materialization.completed", {"materialization": (materialization)}
    )

    try:
        with telemetry.measure_stage("graph.observation"):
            observation = observe_semantic_triples(
                graphdb=graphdb, source_unit_ids=(support_source_ids)
            )
    except Exception as error:
        return _failure(
            case=case,
            configuration=configuration,
            stage="graph_observation",
            error_type=(type(error).__name__),
            error_message=str(error),
            telemetry=telemetry,
            partial={
                "support_source_ids": list(support_source_ids),
                "graph_extractions": (_reference_extractions_to_dict(graph_outcome)),
                "extraction_measurements": (extraction_measurements.to_dict()),
                "materialization": (materialization.to_dict()),
            },
        )

    expected_graphs = {str(unit_graph_iri(source_id)) for source_id in support_source_ids}

    observed_graphs = set(observation.graph_iris)

    if observed_graphs != expected_graphs:
        return _failure(
            case=case,
            configuration=configuration,
            stage="graph_observation",
            error_type="ValueError",
            error_message=(
                "observed supporting named graphs "
                "do not match the expected "
                "supporting source graphs"
            ),
            telemetry=telemetry,
            partial={
                "expected_graphs": sorted(expected_graphs),
                "observed_graphs": sorted(observed_graphs),
                "observation": (observation.to_dict()),
            },
        )

    if not observation.triples:
        return _failure(
            case=case,
            configuration=configuration,
            stage="graph_observation",
            error_type="ValueError",
            error_message=("supporting graphs contain no semantic triples"),
            telemetry=telemetry,
            partial={"observation": (observation.to_dict())},
        )

    graph_ntriples = "\n".join(triple.to_ntriple() for triple in observation.triples)

    try:
        with telemetry.measure_stage("graph.frozen.measurements"):
            graph_measurements = measure_frozen_graph(
                graph_ntriples, named_graph_count=len(observation.graph_iris)
            )
    except Exception as error:
        return _failure(
            case=case,
            configuration=configuration,
            stage="graph_measurement",
            error_type=(type(error).__name__),
            error_message=str(error),
            telemetry=telemetry,
            partial={"observation": (observation.to_dict()), "graph_ntriples": (graph_ntriples)},
        )

    _emit_progress(
        progress_sink,
        "graph.frozen",
        {"graph_ntriples": (graph_ntriples), "measurements": (graph_measurements)},
    )

    registry = SourceRegistry(sources)

    attempts: list[H0QueryAttemptRecord] = []
    feedback: str | None = None

    for attempt_index in range(1, configuration.max_query_attempts + 1):
        _emit_progress(
            progress_sink,
            "query.attempt.started",
            {
                "attempt_index": attempt_index,
                "max_attempts": configuration.max_query_attempts,
                "has_feedback": feedback is not None,
            },
        )

        try:
            with telemetry.measure_stage("query.reference.generation", attempt_index=attempt_index):
                generation = generate_reference_query(
                    case=case,
                    graph_ntriples=graph_ntriples,
                    feedback=feedback,
                    generate_response=query_generate_response,
                )
        except ReferenceQueryValidationError as error:
            # Mechanical interface recovery only.
            #
            # No gold answer, provenance coverage, or reasoning judgment
            # participates in this retry.
            feedback = validation_feedback(response=error.response, error=error.validation_error)

            _emit_progress(
                progress_sink,
                "query.validation.failed",
                {
                    "attempt_index": attempt_index,
                    "error": str(error.validation_error),
                    "response": error.response,
                },
            )

            attempts.append(
                H0QueryAttemptRecord(
                    attempt_index=attempt_index,
                    prompt=error.prompt,
                    response=error.response,
                    validation_error=str(error.validation_error),
                    feedback=feedback,
                )
            )

            continue

        except Exception as error:
            return _failure(
                case=case,
                configuration=configuration,
                stage="query_generation",
                error_type=type(error).__name__,
                error_message=str(error),
                telemetry=telemetry,
                partial=_partial_success_state(
                    support_source_ids=support_source_ids,
                    graph_outcome=graph_outcome,
                    extraction_measurements=extraction_measurements,
                    materialization=materialization,
                    observation=observation,
                    graph_measurements=graph_measurements,
                    query_attempts=tuple(attempts),
                ),
            )

        try:
            execution_sparql = compile_reference_query(
                generation.plan,
                scope=configuration.query_scope,
                support_source_ids=support_source_ids,
            )
        except Exception as error:
            attempts.append(
                H0QueryAttemptRecord(
                    attempt_index=attempt_index,
                    prompt=generation.prompt,
                    response=generation.response,
                    plan=generation.plan,
                )
            )

            return _failure(
                case=case,
                configuration=configuration,
                stage="query_execution",
                error_type=type(error).__name__,
                error_message=str(error),
                telemetry=telemetry,
                partial=_partial_success_state(
                    support_source_ids=support_source_ids,
                    graph_outcome=graph_outcome,
                    extraction_measurements=extraction_measurements,
                    materialization=materialization,
                    observation=observation,
                    graph_measurements=graph_measurements,
                    query_attempts=tuple(attempts),
                ),
            )

        _emit_progress(
            progress_sink,
            "query.generated",
            {
                "attempt_index": attempt_index,
                "generation": generation,
                "execution_sparql": execution_sparql,
            },
        )

        try:
            with telemetry.measure_stage("graphdb.semantic", attempt_index=attempt_index):
                original_result = graphdb.query(execution_sparql)
        except Exception as error:
            attempts.append(
                H0QueryAttemptRecord(
                    attempt_index=attempt_index,
                    prompt=generation.prompt,
                    response=generation.response,
                    plan=generation.plan,
                    execution_sparql=execution_sparql,
                )
            )

            return _failure(
                case=case,
                configuration=configuration,
                stage="query_execution",
                error_type=type(error).__name__,
                error_message=str(error),
                telemetry=telemetry,
                partial=_partial_success_state(
                    support_source_ids=support_source_ids,
                    graph_outcome=graph_outcome,
                    extraction_measurements=extraction_measurements,
                    materialization=materialization,
                    observation=observation,
                    graph_measurements=graph_measurements,
                    query_attempts=tuple(attempts),
                ),
            )

        terms = answer_terms(original_result)

        observed_answers = tuple(display_answer_term(term) for term in terms)

        # Collection records what happened.
        #
        # It deliberately does NOT decide here whether these answers
        # are equivalent to the benchmark answer.
        _emit_progress(
            progress_sink,
            "query.executed",
            {
                "attempt_index": attempt_index,
                "observed_answers": observed_answers,
                "result": original_result,
            },
        )

        # Provenance is attempted for every successfully executed query.
        #
        # It is NOT conditional on benchmark answer correctness.
        _emit_progress(progress_sink, "provenance.started", {"attempt_index": attempt_index})

        try:
            with telemetry.measure_stage("provenance.execution", attempt_index=attempt_index):
                provenance_attempt = execute_qa_query_attempt(
                    turn_index=attempt_index,
                    purpose="final",
                    semantic_sparql=generation.plan.semantic_sparql,
                    scoped_sparql=execution_sparql,
                    graphdb=graphdb,
                    npcs=npcs,
                    registry=registry,
                )
        except Exception as error:
            attempts.append(
                H0QueryAttemptRecord(
                    attempt_index=attempt_index,
                    prompt=generation.prompt,
                    response=generation.response,
                    plan=generation.plan,
                    execution_sparql=execution_sparql,
                    original_result=original_result,
                    observed_answers=observed_answers,
                )
            )

            return _failure(
                case=case,
                configuration=configuration,
                stage="provenance",
                error_type=type(error).__name__,
                error_message=str(error),
                telemetry=telemetry,
                partial=_partial_success_state(
                    support_source_ids=support_source_ids,
                    graph_outcome=graph_outcome,
                    extraction_measurements=extraction_measurements,
                    materialization=materialization,
                    observation=observation,
                    graph_measurements=graph_measurements,
                    query_attempts=tuple(attempts),
                ),
            )

        # A returned provenance status is itself an observation.
        #
        # The collector does not require provenance_status == "decoded"
        # in order to call the collection complete.
        _emit_progress(
            progress_sink,
            "provenance.completed",
            {"attempt_index": attempt_index, "provenance": provenance_attempt},
        )

        attempts.append(
            H0QueryAttemptRecord(
                attempt_index=attempt_index,
                prompt=generation.prompt,
                response=generation.response,
                plan=generation.plan,
                execution_sparql=execution_sparql,
                original_result=original_result,
                observed_answers=observed_answers,
                provenance=provenance_attempt,
            )
        )

        # First mechanically valid and executable query is the observation.
        #
        # No gold-answer-conditioned retry.
        # No gold-support-conditioned retry.
        return H0CaseResult(
            case_id=case.case_id,
            question=case.question,
            expected_answer=case.answer,
            hop_count=case.hop_count,
            configuration=configuration,
            support_source_ids=support_source_ids,
            graph_extractions=graph_outcome,
            extraction_measurements=extraction_measurements,
            materialization=materialization,
            observation=observation,
            graph_measurements=graph_measurements,
            query_attempts=tuple(attempts),
            final_provenance=provenance_attempt,
            telemetry=telemetry.snapshot(),
        )

    return _failure(
        case=case,
        configuration=configuration,
        stage="query_generation",
        error_type="QueryResponseContractExhausted",
        error_message=(
            "query agent did not produce a mechanically valid response "
            f"within {configuration.max_query_attempts} attempts"
        ),
        telemetry=telemetry,
        partial=_partial_success_state(
            support_source_ids=support_source_ids,
            graph_outcome=graph_outcome,
            extraction_measurements=extraction_measurements,
            materialization=materialization,
            observation=observation,
            graph_measurements=graph_measurements,
            query_attempts=tuple(attempts),
        ),
    )


def _failure(
    *,
    case: MusiqueCase,
    configuration: ExperimentConfig,
    stage: H0FailureStage,
    error_type: str,
    error_message: str,
    telemetry: ExperimentTelemetryRecorder,
    partial: dict[str, object],
) -> H0CaseFailure:
    return H0CaseFailure(
        case_id=case.case_id,
        question=case.question,
        expected_answer=case.answer,
        hop_count=case.hop_count,
        configuration=configuration,
        stage=stage,
        error_type=error_type,
        error_message=error_message,
        telemetry=telemetry.snapshot(),
        partial=partial,
    )


def _partial_success_state(
    *,
    support_source_ids: tuple[str, ...],
    graph_outcome: (ReferenceGraphExtractionResult),
    extraction_measurements: (ReferenceExtractionMeasurements),
    materialization: (GraphMaterializationSummary),
    observation: QAAgentObservation,
    graph_measurements: (FrozenGraphMeasurements),
    query_attempts: tuple[H0QueryAttemptRecord, ...],
) -> dict[str, object]:
    return {
        "support_source_ids": list(support_source_ids),
        "graph_extractions": (_reference_extractions_to_dict(graph_outcome)),
        "extraction_measurements": (extraction_measurements.to_dict()),
        "materialization": (materialization.to_dict()),
        "observation": (observation.to_dict()),
        "graph_measurements": (graph_measurements.to_dict()),
        "query_attempts": [attempt.to_dict() for attempt in query_attempts],
    }


def _reference_extractions_to_dict(result: ReferenceGraphExtractionResult) -> dict[str, object]:
    return {
        "attempt_count": (result.attempt_count),
        "retry_count": (result.retry_count),
        "items": [
            {
                "paragraph_index": (item.paragraph_index),
                "attempt_count": (item.attempt_count),
                "run": (_extraction_run_to_dict(item.run)),
            }
            for item in result.items
        ],
    }


def _reference_failure_to_dict(failure: (ReferenceGraphExtractionFailure)) -> dict[str, object]:
    return {
        "paragraph_index": (failure.paragraph_index),
        "source_unit_id": (failure.source_unit_id),
        "attempt_count": (failure.attempt_count),
        "failure": {
            "source": {
                "unit_id": (failure.failure.source.unit_id),
                "title": (failure.failure.source.title),
                "text": (failure.failure.source.text),
            },
            "prompt": (failure.failure.prompt),
            "response": (failure.failure.response),
            "stage": (failure.failure.stage),
            "error_type": (failure.failure.error_type),
            "error_message": (failure.failure.error_message),
        },
        "completed_items": [
            {
                "paragraph_index": (item.paragraph_index),
                "attempt_count": (item.attempt_count),
                "run": (_extraction_run_to_dict(item.run)),
            }
            for item in failure.completed_items
        ],
    }


def _extraction_run_to_dict(run: GroundedExtractionRun) -> dict[str, object]:
    return {
        "source": {
            "unit_id": (run.source.unit_id),
            "title": run.source.title,
            "text": run.source.text,
        },
        "prompt": run.prompt,
        "response": run.response,
        "extraction": (run.extraction.to_dict()),
        "correction": (_correction_to_dict(run.correction) if run.correction is not None else None),
    }


def _correction_to_dict(correction: (GroundedExtractionCorrection)) -> dict[str, object]:
    return {
        "prompt": correction.prompt,
        "response": correction.response,
        "requested_rejections": [
            rejection.to_dict() for rejection in correction.requested_rejections
        ],
        "initial_valid_statement_count": (correction.initial_valid_statement_count),
        "corrected_valid_statement_count": (correction.corrected_valid_statement_count),
        "remaining_rejections": [
            rejection.to_dict() for rejection in correction.remaining_rejections
        ],
        "error_type": (correction.error_type),
        "error_message": (correction.error_message),
    }


def _configuration_to_dict(configuration: ExperimentConfig) -> dict[str, object]:
    return {
        "graph_origin": (configuration.graph_origin.value),
        "query_origin": (configuration.query_origin.value),
        "query_scope": (configuration.query_scope.value),
        "max_source_attempts": (configuration.max_source_attempts),
        "max_query_attempts": (configuration.max_query_attempts),
    }


def _emit_progress(sink: H0ProgressSink | None, event: str, payload: dict[str, object]) -> None:
    if sink is not None:
        sink(event, payload)
