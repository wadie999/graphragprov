"""Execution of configurable multi-turn graph QA agents."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import cast

from graphragprov.graphdb import GraphDBClient
from graphragprov.npcs import NPCSClient
from graphragprov.provenance import SourceRegistry, decode_provenance_polynomial
from graphragprov.qaagent.config import QAAgentConfiguration
from graphragprov.qaagent.observation import QAAgentObservation, observe_semantic_triples
from graphragprov.qaagent.prompt import build_tuple_qa_prompt
from graphragprov.qaagent.response import QAAgentDecision, parse_qa_agent_response
from graphragprov.qaagent.scope import compile_scoped_select_query
from graphragprov.qaagent.trace import QAAnswerProvenance, QAQueryAttempt
from graphragprov.query import PROVENANCE_VARIABLE, execute_provenance_query

GenerateQAResponse = Callable[[str], str]


@dataclass(frozen=True, slots=True)
class QAAgentRunResult:
    """Complete observable result of one multi-turn QA-agent run.

    ``prompt``, ``raw_response``, and ``decision`` describe the final agent
    turn. ``query_attempts`` preserves every executed query in order.
    """

    configuration: QAAgentConfiguration
    observation: QAAgentObservation
    prompt: str
    raw_response: str
    decision: QAAgentDecision
    query_attempts: tuple[QAQueryAttempt, ...]

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
            "configuration": (self.configuration.to_dict()),
            "observation": self.observation.to_dict(),
            "prompt": self.prompt,
            "raw_response": self.raw_response,
            "decision": self.decision.to_dict(),
            "query_attempts": [attempt.to_dict() for attempt in self.query_attempts],
        }


def run_tuple_qa_agent(
    *,
    question: str,
    hop_count: int,
    configuration: QAAgentConfiguration,
    source_unit_ids: Iterable[str] | None,
    graphdb: GraphDBClient,
    npcs: NPCSClient,
    registry: SourceRegistry,
    generate_response: GenerateQAResponse,
    expected_answer: str | None = None,
    decomposition: tuple[str, ...] = (),
) -> QAAgentRunResult:
    """Run a bounded tuple-context QA loop over GraphDB.

    The semantic graph observation is loaded once. After each unsuccessful
    query, the next model turn receives the previous semantic SPARQL,
    decision, provenance status, and actual GraphDB response.
    """

    if configuration.context_mode != "tuples":
        raise NotImplementedError("the current runner supports only context_mode='tuples'")

    resolved_unit_ids = None if source_unit_ids is None else tuple(source_unit_ids)

    _validate_scope(configuration=configuration, source_unit_ids=resolved_unit_ids)

    observation = observe_semantic_triples(graphdb=graphdb, source_unit_ids=resolved_unit_ids)

    base_prompt = build_tuple_qa_prompt(
        question=question,
        hop_count=hop_count,
        observation=observation,
        configuration=configuration,
        expected_answer=expected_answer,
        decomposition=decomposition,
    )

    attempts: list[QAQueryAttempt] = []
    completed_turns: list[tuple[QAAgentDecision, QAQueryAttempt]] = []

    final_prompt: str | None = None
    final_raw_response: str | None = None
    final_decision: QAAgentDecision | None = None

    for turn_index in range(1, configuration.max_turns + 1):
        prompt = _build_turn_prompt(
            base_prompt=base_prompt,
            completed_turns=completed_turns,
            turn_index=turn_index,
            max_turns=configuration.max_turns,
        )

        raw_response = generate_response(prompt)
        decision = parse_qa_agent_response(raw_response)

        final_prompt = prompt
        final_raw_response = raw_response
        final_decision = decision

        if decision.status != "query":
            return QAAgentRunResult(
                configuration=configuration,
                observation=observation,
                prompt=prompt,
                raw_response=raw_response,
                decision=decision,
                query_attempts=tuple(attempts),
            )

        assert decision.sparql is not None

        semantic_sparql = decision.sparql.strip()

        scoped_sparql = compile_scoped_select_query(
            semantic_sparql, source_unit_ids=resolved_unit_ids
        )

        attempt = execute_qa_query_attempt(
            turn_index=turn_index,
            semantic_sparql=semantic_sparql,
            scoped_sparql=scoped_sparql,
            graphdb=graphdb,
            npcs=npcs,
            registry=registry,
        )

        attempts.append(attempt)

        if attempt.provenance_status == "decoded":
            return QAAgentRunResult(
                configuration=configuration,
                observation=observation,
                prompt=prompt,
                raw_response=raw_response,
                decision=decision,
                query_attempts=tuple(attempts),
            )

        completed_turns.append((decision, attempt))

    if final_prompt is None or final_raw_response is None or final_decision is None:
        raise AssertionError("QA-agent configuration allowed no turns")

    return QAAgentRunResult(
        configuration=configuration,
        observation=observation,
        prompt=final_prompt,
        raw_response=final_raw_response,
        decision=final_decision,
        query_attempts=tuple(attempts),
    )


def execute_qa_query_attempt(
    *,
    turn_index: int,
    semantic_sparql: str,
    scoped_sparql: str,
    graphdb: GraphDBClient,
    npcs: NPCSClient,
    registry: SourceRegistry,
) -> QAQueryAttempt:
    """Execute and provenance-decode one QA query attempt."""

    if turn_index < 1:
        raise ValueError("query-attempt turn index must be positive")

    try:
        execution = execute_provenance_query(sparql=scoped_sparql, graphdb=graphdb, npcs=npcs)
    except Exception as error:
        return QAQueryAttempt(
            turn_index=turn_index,
            purpose="final",
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
                purpose="final",
                semantic_sparql=semantic_sparql,
                scoped_sparql=scoped_sparql,
                execution=execution,
                provenance_status="no_answers",
            )

        if not original_bindings:
            raise ValueError(
                "rewritten query returned answers while the original query returned none"
            )

        if not rewritten_bindings:
            raise ValueError(
                "original query returned answers but the rewritten provenance query returned none"
            )

        answer_provenances = tuple(
            _decode_answer_provenance(binding, registry=registry) for binding in rewritten_bindings
        )
    except Exception as error:
        return QAQueryAttempt(
            turn_index=turn_index,
            purpose="final",
            semantic_sparql=semantic_sparql,
            scoped_sparql=scoped_sparql,
            execution=execution,
            provenance_status="failed",
            error_type=type(error).__name__,
            error_message=str(error),
        )

    return QAQueryAttempt(
        turn_index=turn_index,
        purpose="final",
        semantic_sparql=semantic_sparql,
        scoped_sparql=scoped_sparql,
        execution=execution,
        answer_provenances=answer_provenances,
        provenance_status="decoded",
    )


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
            "execution_feedback": (_query_attempt_feedback(attempt)),
        }
        for decision, attempt in completed_turns
    ]

    return "\n".join(
        [
            base_prompt,
            "",
            "MULTI-TURN EXECUTION FEEDBACK",
            (f"You are now on turn {turn_index} of at most {max_turns}."),
            ("The previous SPARQL queries were executed against the real scoped GraphDB dataset."),
            (
                "Use the database responses below as feedback. "
                "Diagnose entity identity, predicate, join, or "
                "query-shape problems and revise the query."
            ),
            ("Do not repeat an unsuccessful query unchanged."),
            ("Return exactly the same JSON decision schema required by the original instructions."),
            "",
            "Previous turns:",
            json.dumps(history_payload, ensure_ascii=False, indent=2, sort_keys=True),
        ]
    )


def _query_attempt_feedback(attempt: QAQueryAttempt) -> dict[str, object]:
    """Return concise model-facing feedback from one real query execution."""

    feedback: dict[str, object] = {
        "semantic_sparql": (attempt.semantic_sparql),
        "provenance_status": (attempt.provenance_status),
    }

    if attempt.execution is not None:
        feedback["graphdb_result"] = attempt.execution.original_result

    if attempt.error_type is not None:
        feedback["error_type"] = attempt.error_type

    if attempt.error_message is not None:
        feedback["error_message"] = attempt.error_message

    return feedback


def _decode_answer_provenance(
    binding: dict[str, object], *, registry: SourceRegistry
) -> QAAnswerProvenance:
    provenance_binding = binding.get(PROVENANCE_VARIABLE)

    if not isinstance(provenance_binding, dict):
        raise ValueError(f"rewritten answer binding has no {PROVENANCE_VARIABLE!r} value")

    polynomial = provenance_binding.get("value")

    if not isinstance(polynomial, str) or not polynomial.strip():
        raise ValueError("answer provenance polynomial must be a non-empty string")

    answer_binding = {name: value for name, value in binding.items() if name != PROVENANCE_VARIABLE}

    if not answer_binding:
        raise ValueError("rewritten result contains provenance without an answer binding")

    decoded = decode_provenance_polynomial(polynomial, registry=registry)

    return QAAnswerProvenance(binding=answer_binding, polynomial=polynomial, decoded=decoded)


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


def _validate_scope(
    *, configuration: QAAgentConfiguration, source_unit_ids: tuple[str, ...] | None
) -> None:
    if configuration.graph_scope == "repository_all":
        if source_unit_ids is not None:
            raise ValueError("repository_all scope requires source_unit_ids=None")

        return

    if source_unit_ids is None:
        raise ValueError(f"{configuration.graph_scope} scope requires explicit source-unit IDs")

    if not source_unit_ids:
        raise ValueError(f"{configuration.graph_scope} scope requires at least one source-unit ID")
