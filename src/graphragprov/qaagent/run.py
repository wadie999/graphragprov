"""Execution of configurable multi-turn graph QA agents."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Literal, cast

from graphragprov.graphdb import GraphDBClient
from graphragprov.npcs import SparqlProvClient
from graphragprov.provenance import SourceRegistry, decode_provenance_polynomial
from graphragprov.qaagent.config import QAAgentConfiguration
from graphragprov.qaagent.observation import QAAgentObservation, observe_semantic_triples
from graphragprov.qaagent.prompt import build_tuple_qa_prompt
from graphragprov.qaagent.response import QAAgentDecision, parse_qa_agent_response
from graphragprov.qaagent.scope import compile_scoped_select_query
from graphragprov.qaagent.trace import QAAnswerProvenance, QAQueryAttempt, QAQueryPurpose
from graphragprov.query.execution import ProvenanceQueryStage, execute_provenance_query

GenerateQAResponse = Callable[[str], str]

QAAgentEventSink = Callable[[dict[str, object]], None]

QATerminationReason = Literal["final_answer", "agent_decision", "budget_exhausted"]


@dataclass(frozen=True, slots=True)
class QAAgentRunResult:
    """Complete observable result of one multi-turn QA-agent run."""

    configuration: QAAgentConfiguration
    observation: QAAgentObservation | None
    prompt: str
    raw_response: str
    decision: QAAgentDecision
    query_attempts: tuple[QAQueryAttempt, ...]
    termination_reason: QATerminationReason = "budget_exhausted"

    def __post_init__(self) -> None:
        if not self.prompt.strip():
            raise ValueError("QA-agent prompt must not be empty")

        if not self.raw_response.strip():
            raise ValueError("QA-agent raw response must not be empty")

        if len(self.query_attempts) > self.configuration.max_turns:
            raise ValueError("query-attempt count exceeds configured maximum turns")

        expected_turn_indices = tuple(range(1, len(self.query_attempts) + 1))

        actual_turn_indices = tuple(attempt.turn_index for attempt in self.query_attempts)

        if actual_turn_indices != expected_turn_indices:
            raise ValueError("query-attempt turn indices must be consecutive and start at one")

        if self.decision.status == "query" and not self.query_attempts:
            raise ValueError("final query decision requires a query attempt")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable run record."""

        return {
            "configuration": self.configuration.to_dict(),
            "observation": (self.observation.to_dict() if self.observation is not None else None),
            "prompt": self.prompt,
            "raw_response": self.raw_response,
            "decision": self.decision.to_dict(),
            "query_attempts": [attempt.to_dict() for attempt in self.query_attempts],
            "termination_reason": self.termination_reason,
        }


def run_tuple_qa_agent(
    *,
    question: str,
    hop_count: int,
    configuration: QAAgentConfiguration,
    source_unit_ids: Iterable[str] | None = None,
    query_source_unit_ids: Iterable[str] | None = None,
    prompt_source_unit_ids: Iterable[str] | None = None,
    graphdb: GraphDBClient,
    npcs: SparqlProvClient,
    registry: SourceRegistry,
    generate_response: GenerateQAResponse,
    expected_answer: str | None = None,
    decomposition: tuple[str, ...] = (),
    event_sink: QAAgentEventSink | None = None,
) -> QAAgentRunResult:
    """Run a bounded multi-turn graph QA loop.

    ``query_source_unit_ids`` controls the backend SPARQL dataset.

    ``prompt_source_unit_ids`` independently controls which semantic
    tuples are loaded into the LLM prompt.

    ``source_unit_ids`` remains temporarily supported for older callers.
    It applies the same source-unit set to both responsibilities.
    """

    if not question.strip():
        raise ValueError("QA question must not be empty")

    resolved_query_unit_ids, resolved_prompt_unit_ids = _resolve_source_unit_ids(
        configuration=configuration,
        source_unit_ids=source_unit_ids,
        query_source_unit_ids=query_source_unit_ids,
        prompt_source_unit_ids=prompt_source_unit_ids,
    )

    _validate_query_scope(
        configuration=configuration, query_source_unit_ids=resolved_query_unit_ids
    )

    _validate_prompt_context(
        configuration=configuration, prompt_source_unit_ids=resolved_prompt_unit_ids
    )

    _emit(
        event_sink,
        "run.started",
        question=question,
        hop_count=hop_count,
        configuration=configuration.to_dict(),
    )

    observation = _load_prompt_observation(
        configuration=configuration,
        prompt_source_unit_ids=resolved_prompt_unit_ids,
        graphdb=graphdb,
        event_sink=event_sink,
    )

    base_prompt = build_tuple_qa_prompt(
        question=question,
        hop_count=hop_count,
        observation=observation,
        configuration=configuration,
        expected_answer=expected_answer,
        decomposition=decomposition,
    )

    _emit(event_sink, "run.prompt_ready", prompt=base_prompt)

    attempts: list[QAQueryAttempt] = []

    completed_turns: list[tuple[QAAgentDecision, QAQueryAttempt]] = []

    final_prompt: str | None = None
    final_raw_response: str | None = None
    final_decision: QAAgentDecision | None = None

    for turn_index in range(1, configuration.max_turns + 1):
        _emit(event_sink, "turn.started", turn_index=turn_index, max_turns=configuration.max_turns)

        prompt = _build_turn_prompt(
            base_prompt=base_prompt,
            completed_turns=completed_turns,
            turn_index=turn_index,
            max_turns=configuration.max_turns,
        )

        raw_response = generate_response(prompt)

        _emit(
            event_sink, "turn.response_received", turn_index=turn_index, raw_response=raw_response
        )

        decision = parse_qa_agent_response(raw_response)

        _emit(
            event_sink, "turn.decision_received", turn_index=turn_index, decision=decision.to_dict()
        )

        final_prompt = prompt
        final_raw_response = raw_response
        final_decision = decision

        if decision.status != "query":
            return _complete_run(
                configuration=configuration,
                observation=observation,
                prompt=prompt,
                raw_response=raw_response,
                decision=decision,
                attempts=attempts,
                termination_reason="agent_decision",
                event_sink=event_sink,
            )

        assert decision.sparql is not None
        assert decision.purpose is not None

        purpose = decision.purpose

        semantic_sparql = decision.sparql.strip()

        _emit(
            event_sink,
            "turn.query_generated",
            turn_index=turn_index,
            purpose=purpose,
            semantic_sparql=semantic_sparql,
        )

        scoped_sparql = compile_scoped_select_query(
            semantic_sparql, source_unit_ids=resolved_query_unit_ids
        )

        _emit(
            event_sink,
            "turn.query_scoped",
            turn_index=turn_index,
            purpose=purpose,
            semantic_sparql=semantic_sparql,
            scoped_sparql=scoped_sparql,
        )

        attempt = execute_qa_query_attempt(
            turn_index=turn_index,
            purpose=purpose,
            semantic_sparql=semantic_sparql,
            scoped_sparql=scoped_sparql,
            graphdb=graphdb,
            npcs=npcs,
            registry=registry,
            event_sink=event_sink,
        )

        attempts.append(attempt)

        _emit(
            event_sink,
            "turn.completed",
            turn_index=turn_index,
            purpose=purpose,
            attempt=attempt.to_dict(),
        )

        if purpose == "final" and attempt.provenance_status == "decoded":
            return _complete_run(
                configuration=configuration,
                observation=observation,
                prompt=prompt,
                raw_response=raw_response,
                decision=decision,
                attempts=attempts,
                termination_reason="final_answer",
                event_sink=event_sink,
            )

        completed_turns.append((decision, attempt))

    if final_prompt is None or final_raw_response is None or final_decision is None:
        raise AssertionError("QA-agent configuration allowed no turns")

    return _complete_run(
        configuration=configuration,
        observation=observation,
        prompt=final_prompt,
        raw_response=final_raw_response,
        decision=final_decision,
        attempts=attempts,
        termination_reason="budget_exhausted",
        event_sink=event_sink,
    )


def execute_qa_query_attempt(
    *,
    turn_index: int,
    purpose: QAQueryPurpose,
    semantic_sparql: str,
    scoped_sparql: str,
    graphdb: GraphDBClient,
    npcs: SparqlProvClient,
    registry: SourceRegistry,
    event_sink: QAAgentEventSink | None = None,
) -> QAQueryAttempt:
    """Execute and provenance-decode one QA query attempt."""

    if turn_index < 1:
        raise ValueError("query-attempt turn index must be positive")

    def relay_query_event(stage: ProvenanceQueryStage, payload: dict[str, object]) -> None:
        _emit(event_sink, f"turn.query.{stage}", turn_index=turn_index, purpose=purpose, **payload)

    try:
        execution = execute_provenance_query(
            sparql=scoped_sparql,
            graphdb=graphdb,
            npcs=npcs,
            event_sink=(relay_query_event if event_sink is not None else None),
        )
    except Exception as error:
        return QAQueryAttempt(
            turn_index=turn_index,
            purpose=purpose,
            semantic_sparql=semantic_sparql,
            scoped_sparql=scoped_sparql,
            provenance_status="failed",
            error_type=type(error).__name__,
            error_message=str(error),
        )

    try:
        original_bindings = _bindings(execution.original_result, result_name="original")

        rewritten_bindings = _bindings(execution.rewritten_result, result_name="rewritten")

        if not original_bindings and not rewritten_bindings:
            return QAQueryAttempt(
                turn_index=turn_index,
                purpose=purpose,
                semantic_sparql=semantic_sparql,
                scoped_sparql=scoped_sparql,
                execution=execution,
                provenance_status="no_answers",
            )

        if not original_bindings:
            raise ValueError(
                "rewritten query returned bindings while the original query returned none"
            )

        if not rewritten_bindings:
            raise ValueError(
                "original query returned bindings while "
                "the rewritten provenance query returned none"
            )

        answer_provenances = tuple(
            _decode_answer_provenance(
                binding, registry=registry, provenance_variable=execution.provenance_variable
            )
            for binding in rewritten_bindings
        )
    except Exception as error:
        return QAQueryAttempt(
            turn_index=turn_index,
            purpose=purpose,
            semantic_sparql=semantic_sparql,
            scoped_sparql=scoped_sparql,
            execution=execution,
            provenance_status="failed",
            error_type=type(error).__name__,
            error_message=str(error),
        )

    return QAQueryAttempt(
        turn_index=turn_index,
        purpose=purpose,
        semantic_sparql=semantic_sparql,
        scoped_sparql=scoped_sparql,
        execution=execution,
        answer_provenances=answer_provenances,
        provenance_status="decoded",
    )


def _load_prompt_observation(
    *,
    configuration: QAAgentConfiguration,
    prompt_source_unit_ids: tuple[str, ...] | None,
    graphdb: GraphDBClient,
    event_sink: QAAgentEventSink | None,
) -> QAAgentObservation | None:
    if configuration.context_mode == "graph_agent":
        _emit(
            event_sink,
            "run.context_ready",
            context_mode="graph_agent",
            tuple_count=0,
            graph_iris=[],
        )

        return None

    if configuration.context_mode != "tuples":
        raise NotImplementedError("hybrid prompt context is not implemented")

    _emit(event_sink, "run.context_loading", context_mode="tuples")

    observation = observe_semantic_triples(graphdb=graphdb, source_unit_ids=prompt_source_unit_ids)

    _emit(
        event_sink,
        "run.context_ready",
        context_mode="tuples",
        tuple_count=len(observation.triples),
        graph_iris=list(observation.graph_iris),
    )

    return observation


def _build_turn_prompt(
    *,
    base_prompt: str,
    completed_turns: list[tuple[QAAgentDecision, QAQueryAttempt]],
    turn_index: int,
    max_turns: int,
) -> str:
    """Append real execution feedback for a subsequent agent turn."""

    if not completed_turns:
        return base_prompt

    history_payload = [
        {
            "turn": attempt.turn_index,
            "decision": decision.to_dict(),
            "execution_feedback": _query_attempt_feedback(attempt),
        }
        for decision, attempt in completed_turns
    ]

    return "\n".join(
        [
            base_prompt,
            "",
            "MULTI-TURN EXECUTION FEEDBACK",
            (f"You are now on turn {turn_index} of at most {max_turns}."),
            "",
            "Every previous query below was executed against "
            "the real backend-scoped GraphDB dataset.",
            "",
            "Inspection and candidate results are evidence for constructing the next query.",
            "",
            "A failed or empty query does not imply that the question is unanswerable.",
            "",
            "Use the results to inspect entities, predicates, "
            "identity choices, joins, and query shape.",
            "",
            "Do not repeat an unsuccessful query unchanged.",
            "",
            "Return exactly the same JSON decision schema required by the original instructions.",
            "",
            "Previous turns:",
            json.dumps(history_payload, ensure_ascii=False, indent=2, sort_keys=True),
        ]
    )


def _query_attempt_feedback(attempt: QAQueryAttempt) -> dict[str, object]:
    """Return model-facing feedback from one real query execution."""

    feedback: dict[str, object] = {
        "purpose": attempt.purpose,
        "semantic_sparql": attempt.semantic_sparql,
        "scoped_sparql": attempt.scoped_sparql,
        "provenance_status": attempt.provenance_status,
    }

    if attempt.execution is not None:
        feedback["graphdb_result"] = attempt.execution.original_result

    if attempt.error_type is not None:
        feedback["error_type"] = attempt.error_type

    if attempt.error_message is not None:
        feedback["error_message"] = attempt.error_message

    return feedback


def _decode_answer_provenance(
    binding: dict[str, object],
    *,
    registry: SourceRegistry,
    provenance_variable: str,
) -> QAAnswerProvenance:
    provenance_binding = binding.get(provenance_variable)

    if not isinstance(provenance_binding, dict):
        raise ValueError(f"rewritten result binding has no {provenance_variable!r} value")

    polynomial = provenance_binding.get("value")

    if not isinstance(polynomial, str) or not polynomial.strip():
        raise ValueError("result provenance polynomial must be a non-empty string")

    result_binding = {name: value for name, value in binding.items() if name != provenance_variable}

    if not result_binding:
        raise ValueError("rewritten result contains provenance without a semantic result binding")

    decoded = decode_provenance_polynomial(polynomial, registry=registry)

    return QAAnswerProvenance(binding=result_binding, polynomial=polynomial, decoded=decoded)


def _bindings(result: dict[str, object], *, result_name: str) -> tuple[dict[str, object], ...]:
    raw_results = result.get("results")

    if not isinstance(raw_results, dict):
        raise ValueError(f"{result_name} query result has no results object")

    raw_bindings = raw_results.get("bindings")

    if not isinstance(raw_bindings, list):
        raise ValueError(f"{result_name} query result has no bindings list")

    bindings: list[dict[str, object]] = []

    for index, binding in enumerate(raw_bindings):
        if not isinstance(binding, dict):
            raise ValueError(f"{result_name} query binding {index} must be an object")

        bindings.append(cast(dict[str, object], binding))

    return tuple(bindings)


def _resolve_source_unit_ids(
    *,
    configuration: QAAgentConfiguration,
    source_unit_ids: Iterable[str] | None,
    query_source_unit_ids: Iterable[str] | None,
    prompt_source_unit_ids: Iterable[str] | None,
) -> tuple[tuple[str, ...] | None, tuple[str, ...] | None]:
    legacy_ids = None if source_unit_ids is None else tuple(source_unit_ids)

    explicit_query_ids = None if query_source_unit_ids is None else tuple(query_source_unit_ids)

    explicit_prompt_ids = None if prompt_source_unit_ids is None else tuple(prompt_source_unit_ids)

    if legacy_ids is not None:
        if explicit_query_ids is not None or explicit_prompt_ids is not None:
            raise ValueError(
                "source_unit_ids cannot be combined with "
                "query_source_unit_ids or prompt_source_unit_ids"
            )

        return (legacy_ids, (legacy_ids if configuration.context_mode == "tuples" else None))

    return (explicit_query_ids, explicit_prompt_ids)


def _validate_query_scope(
    *, configuration: QAAgentConfiguration, query_source_unit_ids: tuple[str, ...] | None
) -> None:
    if configuration.graph_scope == "repository_all":
        if query_source_unit_ids is not None:
            raise ValueError("repository_all scope requires query_source_unit_ids=None")

        return

    if query_source_unit_ids is None:
        raise ValueError(
            f"{configuration.graph_scope} scope requires explicit query source-unit IDs"
        )

    if not query_source_unit_ids:
        raise ValueError(
            f"{configuration.graph_scope} scope requires at least one query source-unit ID"
        )


def _validate_prompt_context(
    *, configuration: QAAgentConfiguration, prompt_source_unit_ids: tuple[str, ...] | None
) -> None:
    if configuration.context_mode == "graph_agent":
        if prompt_source_unit_ids is not None:
            raise ValueError("graph_agent context must not receive prompt source-unit IDs")

        return

    if configuration.context_mode == "tuples":
        if prompt_source_unit_ids is not None and not prompt_source_unit_ids:
            raise ValueError("tuple context requires at least one prompt source unit")

        return

    raise NotImplementedError("hybrid prompt context is not implemented")


def _complete_run(
    *,
    configuration: QAAgentConfiguration,
    observation: QAAgentObservation | None,
    prompt: str,
    raw_response: str,
    decision: QAAgentDecision,
    attempts: list[QAQueryAttempt],
    termination_reason: QATerminationReason,
    event_sink: QAAgentEventSink | None,
) -> QAAgentRunResult:
    result = QAAgentRunResult(
        configuration=configuration,
        observation=observation,
        prompt=prompt,
        raw_response=raw_response,
        decision=decision,
        query_attempts=tuple(attempts),
        termination_reason=termination_reason,
    )

    _emit(
        event_sink, "run.completed", termination_reason=termination_reason, result=result.to_dict()
    )

    return result


def _emit(event_sink: QAAgentEventSink | None, event_type: str, **payload: object) -> None:
    if event_sink is None:
        return

    event_sink({"type": event_type, **payload})
