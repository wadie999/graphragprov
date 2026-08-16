"""Execution of one multi-hop fidelity H0 case."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal, TypeAlias

from graphragprov.benchmarks.musique import MusiqueCase, MusiqueSourceUnit
from graphragprov.experiments.multihop_fidelity.config import ArtifactOrigin, ExperimentConfig
from graphragprov.experiments.multihop_fidelity.graph import (
    ReferenceGraphExtractionFailure,
    ReferenceGraphExtractionResult,
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
    ReferenceQueryGeneration,
    ReferenceQueryPlan,
    ReferenceQueryValidationError,
    answer_matches_case,
    answer_terms,
    compile_reference_query,
    display_answer_term,
    execution_feedback,
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

H0FailureStage = Literal[
    "graph_extraction",
    "graph_measurement",
    "graph_clear",
    "graph_materialization",
    "graph_observation",
    "query_generation",
    "query_execution",
    "provenance",
    "query_attempts_exhausted",
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
        """Return a deterministic JSON-serializable representation."""

        return {
            "attempt_index": self.attempt_index,
            "prompt": self.prompt,
            "response": self.response,
            "plan": (self.plan.to_dict() if self.plan is not None else None),
            "execution_sparql": self.execution_sparql,
            "original_result": self.original_result,
            "observed_answers": list(self.observed_answers),
            "answer_correct": self.answer_correct,
            "validation_error": self.validation_error,
            "provenance": (self.provenance.to_dict() if self.provenance is not None else None),
            "gold_support_covered": (self.gold_support_covered),
            "feedback": self.feedback,
        }


@dataclass(frozen=True, slots=True)
class H0CaseResult:
    """Successful executable H0 result for one MuSiQue case."""

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

        if self.final_provenance.provenance_status != "decoded":
            raise ValueError("successful H0 result requires decoded provenance")

    def to_dict(self) -> dict[str, object]:
        """Return the complete inspectable H0 case artifact."""

        return {
            "status": "success",
            "case_id": self.case_id,
            "question": self.question,
            "expected_answer": self.expected_answer,
            "hop_count": self.hop_count,
            "configuration": _configuration_to_dict(self.configuration),
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
    """Inspectable expected failure of one H0 case."""

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
        """Return the complete inspectable failure artifact."""

        return {
            "status": "failure",
            "case_id": self.case_id,
            "question": self.question,
            "expected_answer": self.expected_answer,
            "hop_count": self.hop_count,
            "configuration": _configuration_to_dict(self.configuration),
            "stage": self.stage,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "telemetry": self.telemetry.to_dict(),
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
) -> H0CaseOutcome:
    """Run one complete H0 reference case.

    H0 requires a reference graph and a reference query. The semantic query is
    generated independently of execution scope; Python applies support or
    repository scope afterwards.
    """

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

    with telemetry.measure_stage("graph.reference.extraction"):
        graph_outcome = construct_reference_extractions(
            case=case,
            sources=sources,
            generate_response=(graph_generate_response),
            max_attempts=(configuration.max_source_attempts),
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
            error_type=type(error).__name__,
            error_message=str(error),
            telemetry=telemetry,
            partial={
                "support_source_ids": list(support_source_ids),
                "graph_extractions": (_reference_extractions_to_dict(graph_outcome)),
            },
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
            error_type=type(error).__name__,
            error_message=str(error),
            telemetry=telemetry,
            partial={
                "support_source_ids": list(support_source_ids),
                "graph_extractions": (_reference_extractions_to_dict(graph_outcome)),
                "extraction_measurements": (extraction_measurements.to_dict()),
            },
        )

    try:
        with telemetry.measure_stage("graph.materialization"):
            materialization = materialize_grounded_extractions(graph_outcome.runs, graphdb=graphdb)
    except Exception as error:
        return _failure(
            case=case,
            configuration=configuration,
            stage="graph_materialization",
            error_type=type(error).__name__,
            error_message=str(error),
            telemetry=telemetry,
            partial={
                "support_source_ids": list(support_source_ids),
                "graph_extractions": (_reference_extractions_to_dict(graph_outcome)),
                "extraction_measurements": (extraction_measurements.to_dict()),
            },
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
            error_type=type(error).__name__,
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
                "observed supporting named graphs do not "
                "match the expected supporting source graphs"
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
            error_type=type(error).__name__,
            error_message=str(error),
            telemetry=telemetry,
            partial={"observation": (observation.to_dict()), "graph_ntriples": (graph_ntriples)},
        )

    registry = SourceRegistry(sources)

    attempts: list[H0QueryAttemptRecord] = []

    feedback: str | None = None

    for attempt_index in range(1, configuration.max_query_attempts + 1):
        try:
            with telemetry.measure_stage("query.reference.generation", attempt_index=attempt_index):
                generation = generate_reference_query(
                    case=case,
                    graph_ntriples=(graph_ntriples),
                    feedback=feedback,
                    generate_response=(query_generate_response),
                )
        except ReferenceQueryValidationError as error:
            feedback = validation_feedback(response=error.response, error=error.validation_error)

            attempts.append(
                H0QueryAttemptRecord(
                    attempt_index=(attempt_index),
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
                    support_source_ids=(support_source_ids),
                    graph_outcome=(graph_outcome),
                    extraction_measurements=(extraction_measurements),
                    materialization=(materialization),
                    observation=observation,
                    graph_measurements=(graph_measurements),
                    query_attempts=tuple(attempts),
                ),
            )

        execution_sparql = compile_reference_query(
            generation.plan,
            scope=(configuration.query_scope),
            support_source_ids=(support_source_ids),
        )

        try:
            with telemetry.measure_stage("graphdb.semantic", attempt_index=attempt_index):
                original_result = graphdb.query(execution_sparql)
        except Exception as error:
            return _failure(
                case=case,
                configuration=configuration,
                stage="query_execution",
                error_type=type(error).__name__,
                error_message=str(error),
                telemetry=telemetry,
                partial=_partial_success_state(
                    support_source_ids=(support_source_ids),
                    graph_outcome=(graph_outcome),
                    extraction_measurements=(extraction_measurements),
                    materialization=(materialization),
                    observation=observation,
                    graph_measurements=(graph_measurements),
                    query_attempts=tuple(attempts),
                ),
            )

        terms = answer_terms(original_result)

        observed_answers = tuple(display_answer_term(term) for term in terms)

        answer_correct = answer_matches_case(case, terms)

        if not answer_correct:
            feedback = execution_feedback(
                case=case,
                scope=(configuration.query_scope),
                plan=generation.plan,
                execution_sparql=(execution_sparql),
                result=original_result,
                terms=terms,
            )

            attempts.append(
                H0QueryAttemptRecord(
                    attempt_index=(attempt_index),
                    prompt=(generation.prompt),
                    response=(generation.response),
                    plan=generation.plan,
                    execution_sparql=(execution_sparql),
                    original_result=(original_result),
                    observed_answers=(observed_answers),
                    answer_correct=False,
                    feedback=feedback,
                )
            )

            continue

        try:
            with telemetry.measure_stage("provenance.execution", attempt_index=attempt_index):
                provenance_attempt = execute_qa_query_attempt(
                    turn_index=(attempt_index),
                    purpose="final",
                    semantic_sparql=(generation.plan.semantic_sparql),
                    scoped_sparql=(execution_sparql),
                    graphdb=graphdb,
                    npcs=npcs,
                    registry=registry,
                )
        except Exception as error:
            return _failure(
                case=case,
                configuration=configuration,
                stage="provenance",
                error_type=type(error).__name__,
                error_message=str(error),
                telemetry=telemetry,
                partial=_partial_success_state(
                    support_source_ids=(support_source_ids),
                    graph_outcome=(graph_outcome),
                    extraction_measurements=(extraction_measurements),
                    materialization=(materialization),
                    observation=observation,
                    graph_measurements=(graph_measurements),
                    query_attempts=tuple(attempts),
                ),
            )

        if provenance_attempt.provenance_status != "decoded":
            attempts.append(
                H0QueryAttemptRecord(
                    attempt_index=(attempt_index),
                    prompt=(generation.prompt),
                    response=(generation.response),
                    plan=generation.plan,
                    execution_sparql=(execution_sparql),
                    original_result=(original_result),
                    observed_answers=(observed_answers),
                    answer_correct=True,
                    provenance=(provenance_attempt),
                )
            )

            return _failure(
                case=case,
                configuration=configuration,
                stage="provenance",
                error_type=(provenance_attempt.error_type or "ProvenanceError"),
                error_message=(
                    provenance_attempt.error_message
                    or ("provenance execution did not produce decoded provenance")
                ),
                telemetry=telemetry,
                partial=_partial_success_state(
                    support_source_ids=(support_source_ids),
                    graph_outcome=(graph_outcome),
                    extraction_measurements=(extraction_measurements),
                    materialization=(materialization),
                    observation=observation,
                    graph_measurements=(graph_measurements),
                    query_attempts=tuple(attempts),
                ),
            )

        support_covered = _covers_gold_support(case, provenance_attempt)

        if support_covered:
            attempts.append(
                H0QueryAttemptRecord(
                    attempt_index=(attempt_index),
                    prompt=(generation.prompt),
                    response=(generation.response),
                    plan=generation.plan,
                    execution_sparql=(execution_sparql),
                    original_result=(original_result),
                    observed_answers=(observed_answers),
                    answer_correct=True,
                    provenance=(provenance_attempt),
                    gold_support_covered=True,
                )
            )

            return H0CaseResult(
                case_id=case.case_id,
                question=case.question,
                expected_answer=case.answer,
                hop_count=case.hop_count,
                configuration=configuration,
                support_source_ids=(support_source_ids),
                graph_extractions=(graph_outcome),
                extraction_measurements=(extraction_measurements),
                materialization=(materialization),
                observation=observation,
                graph_measurements=(graph_measurements),
                query_attempts=tuple(attempts),
                final_provenance=(provenance_attempt),
                telemetry=(telemetry.snapshot()),
            )

        feedback = _gold_support_feedback(
            configuration=configuration,
            generation=generation,
            provenance_attempt=(provenance_attempt),
        )

        attempts.append(
            H0QueryAttemptRecord(
                attempt_index=(attempt_index),
                prompt=generation.prompt,
                response=(generation.response),
                plan=generation.plan,
                execution_sparql=(execution_sparql),
                original_result=(original_result),
                observed_answers=(observed_answers),
                answer_correct=True,
                provenance=(provenance_attempt),
                gold_support_covered=False,
                feedback=feedback,
            )
        )

    return _failure(
        case=case,
        configuration=configuration,
        stage="query_attempts_exhausted",
        error_type="RuntimeError",
        error_message=(
            "no reference query satisfied the complete "
            "H0 answer and provenance criteria within "
            f"{configuration.max_query_attempts} attempts"
        ),
        telemetry=telemetry,
        partial=_partial_success_state(
            support_source_ids=(support_source_ids),
            graph_outcome=graph_outcome,
            extraction_measurements=(extraction_measurements),
            materialization=(materialization),
            observation=observation,
            graph_measurements=(graph_measurements),
            query_attempts=tuple(attempts),
        ),
    )


def _covers_gold_support(case: MusiqueCase, attempt: QAQueryAttempt) -> bool:
    expected = {paragraph.unit_id for paragraph in reference_supporting_paragraphs(case)}

    return any(
        expected <= {occurrence.source.unit_id for occurrence in derivation.occurrences}
        for answer in attempt.answer_provenances
        for derivation in answer.decoded.derivations
    )


def _gold_support_feedback(
    *,
    configuration: ExperimentConfig,
    generation: ReferenceQueryGeneration,
    provenance_attempt: QAQueryAttempt,
) -> str:
    return json.dumps(
        {
            "message": (
                "The answer is correct, but no decoded derivation uses all "
                "gold supporting paragraphs. Re-select the exact triples "
                "required by the full decomposition and rebuild the query "
                "from those triples."
            ),
            "query_scope": (configuration.query_scope.value),
            "previous_matched_triples": list(generation.plan.matched_triples),
            "semantic_sparql": (generation.plan.semantic_sparql),
            "provenance_attempt": (provenance_attempt.to_dict()),
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
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
    graph_outcome: ReferenceGraphExtractionResult,
    extraction_measurements: ReferenceExtractionMeasurements,
    materialization: GraphMaterializationSummary,
    observation: QAAgentObservation,
    graph_measurements: FrozenGraphMeasurements,
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
        "attempt_count": result.attempt_count,
        "retry_count": result.retry_count,
        "items": [
            {
                "paragraph_index": (item.paragraph_index),
                "attempt_count": (item.attempt_count),
                "run": (_extraction_run_to_dict(item.run)),
            }
            for item in result.items
        ],
    }


def _reference_failure_to_dict(failure: ReferenceGraphExtractionFailure) -> dict[str, object]:
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
            "unit_id": run.source.unit_id,
            "title": run.source.title,
            "text": run.source.text,
        },
        "prompt": run.prompt,
        "response": run.response,
        "extraction": (run.extraction.to_dict()),
        "correction": (_correction_to_dict(run.correction) if run.correction is not None else None),
    }


def _correction_to_dict(correction: GroundedExtractionCorrection) -> dict[str, object]:
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
        "error_type": correction.error_type,
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
