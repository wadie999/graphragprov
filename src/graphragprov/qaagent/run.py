"""Execution of one-shot graph QA agents."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import cast

from graphragprov.graphdb import GraphDBClient
from graphragprov.npcs import NPCSClient
from graphragprov.provenance import (
    SourceRegistry,
    decode_provenance_polynomial,
)
from graphragprov.qaagent.config import QAAgentConfiguration
from graphragprov.qaagent.observation import (
    QAAgentObservation,
    observe_semantic_triples,
)
from graphragprov.qaagent.prompt import build_tuple_qa_prompt
from graphragprov.qaagent.response import (
    QAAgentDecision,
    parse_qa_agent_response,
)
from graphragprov.qaagent.scope import (
    compile_scoped_select_query,
)
from graphragprov.qaagent.trace import (
    QAAnswerProvenance,
    QAQueryAttempt,
)
from graphragprov.query import (
    PROVENANCE_VARIABLE,
    execute_provenance_query,
)

GenerateQAResponse = Callable[[str], str]


@dataclass(frozen=True, slots=True)
class QAAgentRunResult:
    """Complete observable result of one QA-agent run."""

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

        if self.decision.status == "query":
            if len(self.query_attempts) != 1:
                raise ValueError("one-shot query decision requires one query attempt")
        elif self.query_attempts:
            raise ValueError("non-query decision must not contain query attempts")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable run record."""

        return {
            "configuration": self.configuration.to_dict(),
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
    """Run one tuple-context DeepSeek QA turn over GraphDB."""

    if configuration.context_mode != "tuples":
        raise NotImplementedError("the current runner supports only context_mode='tuples'")

    if configuration.max_turns != 1:
        raise NotImplementedError("the current tuple runner supports exactly one turn")

    resolved_unit_ids = None if source_unit_ids is None else tuple(source_unit_ids)

    _validate_scope(
        configuration=configuration,
        source_unit_ids=resolved_unit_ids,
    )

    observation = observe_semantic_triples(
        graphdb=graphdb,
        source_unit_ids=resolved_unit_ids,
    )

    prompt = build_tuple_qa_prompt(
        question=question,
        hop_count=hop_count,
        observation=observation,
        configuration=configuration,
        expected_answer=expected_answer,
        decomposition=decomposition,
    )

    raw_response = generate_response(prompt)

    decision = parse_qa_agent_response(raw_response)

    if decision.status != "query":
        return QAAgentRunResult(
            configuration=configuration,
            observation=observation,
            prompt=prompt,
            raw_response=raw_response,
            decision=decision,
            query_attempts=(),
        )

    assert decision.sparql is not None

    semantic_sparql = decision.sparql.strip()

    scoped_sparql = compile_scoped_select_query(
        semantic_sparql,
        source_unit_ids=resolved_unit_ids,
    )

    attempt = execute_qa_query_attempt(
        semantic_sparql=semantic_sparql,
        scoped_sparql=scoped_sparql,
        graphdb=graphdb,
        npcs=npcs,
        registry=registry,
    )

    return QAAgentRunResult(
        configuration=configuration,
        observation=observation,
        prompt=prompt,
        raw_response=raw_response,
        decision=decision,
        query_attempts=(attempt,),
    )


def execute_qa_query_attempt(
    *,
    semantic_sparql: str,
    scoped_sparql: str,
    graphdb: GraphDBClient,
    npcs: NPCSClient,
    registry: SourceRegistry,
) -> QAQueryAttempt:
    """Execute and provenance-decode one final QA query."""

    try:
        execution = execute_provenance_query(
            sparql=scoped_sparql,
            graphdb=graphdb,
            npcs=npcs,
        )
    except Exception as error:
        return QAQueryAttempt(
            turn_index=1,
            purpose="final",
            semantic_sparql=semantic_sparql,
            scoped_sparql=scoped_sparql,
            provenance_status="failed",
            error_type=type(error).__name__,
            error_message=str(error),
        )

    try:
        original_bindings = _bindings(
            execution.original_result,
            result_name="original",
        )

        rewritten_bindings = _bindings(
            execution.rewritten_result,
            result_name="rewritten",
        )

        if not original_bindings and not rewritten_bindings:
            return QAQueryAttempt(
                turn_index=1,
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
            _decode_answer_provenance(
                binding,
                registry=registry,
            )
            for binding in rewritten_bindings
        )
    except Exception as error:
        return QAQueryAttempt(
            turn_index=1,
            purpose="final",
            semantic_sparql=semantic_sparql,
            scoped_sparql=scoped_sparql,
            execution=execution,
            provenance_status="failed",
            error_type=type(error).__name__,
            error_message=str(error),
        )

    return QAQueryAttempt(
        turn_index=1,
        purpose="final",
        semantic_sparql=semantic_sparql,
        scoped_sparql=scoped_sparql,
        execution=execution,
        answer_provenances=answer_provenances,
        provenance_status="decoded",
    )


def _decode_answer_provenance(
    binding: dict[str, object],
    *,
    registry: SourceRegistry,
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

    decoded = decode_provenance_polynomial(
        polynomial,
        registry=registry,
    )

    return QAAnswerProvenance(
        binding=answer_binding,
        polynomial=polynomial,
        decoded=decoded,
    )


def _bindings(
    result: dict[str, object],
    *,
    result_name: str,
) -> tuple[dict[str, object], ...]:
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

        bindings.append(
            cast(
                dict[str, object],
                binding,
            )
        )

    return tuple(bindings)


def _validate_scope(
    *,
    configuration: QAAgentConfiguration,
    source_unit_ids: tuple[str, ...] | None,
) -> None:
    if configuration.graph_scope == "repository_all":
        if source_unit_ids is not None:
            raise ValueError("repository_all scope requires source_unit_ids=None")

        return

    if source_unit_ids is None:
        raise ValueError(f"{configuration.graph_scope} scope requires explicit source-unit IDs")

    if not source_unit_ids:
        raise ValueError(f"{configuration.graph_scope} scope requires at least one source-unit ID")
