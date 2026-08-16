"""Reference query construction for multi-hop fidelity experiments."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TypeAlias, cast
from urllib.parse import unquote

from graphragprov.benchmarks.musique import MusiqueCase
from graphragprov.experiments.multihop_fidelity.config import QueryScope
from graphragprov.experiments.prompts import build_musique_sparql_prompt
from graphragprov.extraction.run import GenerateResponse
from graphragprov.qaagent import compile_scoped_select_query
from graphragprov.rdf.terms import ENTITY_NAMESPACE, entity_iri

SPARQLTerm: TypeAlias = dict[str, object]
SPARQLResult: TypeAlias = dict[str, object]


@dataclass(frozen=True, slots=True)
class ReferenceQueryPlan:
    """Mechanically valid query-agent output for one collection attempt."""

    matched_triples: tuple[str, ...]
    semantic_sparql: str

    def __post_init__(self) -> None:
        if not self.semantic_sparql.strip():
            raise ValueError("query plan SPARQL must not be empty")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable representation."""

        return {
            "matched_triples": list(self.matched_triples),
            "semantic_sparql": self.semantic_sparql,
        }


@dataclass(frozen=True, slots=True)
class ReferenceQueryGeneration:
    """One provider generation together with its parsed query plan."""

    prompt: str
    response: str
    plan: ReferenceQueryPlan

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable representation."""

        return {"prompt": self.prompt, "response": self.response, "plan": self.plan.to_dict()}


class ReferenceQueryValidationError(ValueError):
    """A query-agent response that cannot enter the execution interface."""

    def __init__(self, *, prompt: str, response: str, validation_error: ValueError) -> None:
        super().__init__(str(validation_error))

        self.prompt = prompt
        self.response = response
        self.validation_error = validation_error


def generate_reference_query(
    *,
    case: MusiqueCase,
    graph_ntriples: str,
    feedback: str | None,
    generate_response: GenerateResponse,
) -> ReferenceQueryGeneration:
    """Generate and mechanically parse one query-agent response."""

    prompt = build_musique_sparql_prompt(
        case=case, graph_ntriples=graph_ntriples, feedback=feedback
    )

    response = generate_response(prompt)

    try:
        plan = parse_reference_query_plan(response)
    except ValueError as error:
        raise ReferenceQueryValidationError(
            prompt=prompt, response=response, validation_error=error
        ) from error

    return ReferenceQueryGeneration(prompt=prompt, response=response, plan=plan)


def parse_reference_query_plan(response: str) -> ReferenceQueryPlan:
    """Parse the query-agent response without judging its scientific quality.

    Collection requires only enough structure to execute and observe the query.
    Whether claimed evidence exists in the graph, is duplicated, is relevant,
    realizes the decomposition, or supports the answer is evaluated later.
    """

    try:
        decoded: object = json.loads(response)
    except json.JSONDecodeError as error:
        raise ValueError("query response must be valid JSON") from error

    payload = _string_keyed_dict(decoded)

    if payload is None:
        raise ValueError("query response must be a JSON object")

    if set(payload) != {"matched_triples", "sparql"}:
        raise ValueError("query response must contain exactly 'matched_triples' and 'sparql'")

    raw_matched = payload["matched_triples"]

    if not isinstance(raw_matched, list):
        raise ValueError("matched_triples must be a JSON array")

    matched_items: list[str] = []

    for item in raw_matched:
        if not isinstance(item, str):
            raise ValueError("every matched_triples item must be a string")

        matched_items.append(item)

    raw_sparql = payload["sparql"]

    if not isinstance(raw_sparql, str) or not raw_sparql.strip():
        raise ValueError("sparql must be a non-empty string")

    semantic_sparql = raw_sparql.strip()

    normalized = " ".join(semantic_sparql.casefold().split())

    # This is an execution-interface constraint, not a scientific judgment.
    # NPCS currently does not preserve the final provenance projection
    # correctly for SELECT DISTINCT.
    if "select distinct" in normalized:
        raise ValueError(
            "DISTINCT is not supported by the current NPCS provenance execution interface"
        )

    # The collector uses ?answer as the stable answer-binding interface.
    # Semantic equivalence with the benchmark answer is evaluated later.
    if "?answer" not in semantic_sparql:
        raise ValueError("SPARQL must expose the collected answer binding as ?answer")

    return ReferenceQueryPlan(matched_triples=tuple(matched_items), semantic_sparql=semantic_sparql)


def compile_reference_query(
    plan: ReferenceQueryPlan, *, scope: QueryScope, support_source_ids: tuple[str, ...]
) -> str:
    """Apply execution scope outside the query-agent policy."""

    if scope is QueryScope.SUPPORT:
        return compile_scoped_select_query(plan.semantic_sparql, source_unit_ids=support_source_ids)

    if scope is QueryScope.REPOSITORY:
        return plan.semantic_sparql

    raise ValueError(f"unsupported query scope: {scope!r}")


def answer_terms(result: SPARQLResult) -> tuple[SPARQLTerm, ...]:
    """Return unique ?answer RDF terms from a SPARQL JSON result.

    This is representation handling only. It does not compare the result
    against the benchmark answer.
    """

    terms: list[SPARQLTerm] = []

    seen: set[tuple[object, object, object, object]] = set()

    for row in _result_bindings(result):
        term = _string_keyed_dict(row.get("answer"))

        if term is None:
            continue

        key = (term.get("type"), term.get("value"), term.get("datatype"), term.get("xml:lang"))

        if key in seen:
            continue

        seen.add(key)
        terms.append(term)

    return tuple(terms)


def answer_matches_case(case: MusiqueCase, terms: tuple[SPARQLTerm, ...]) -> bool:
    """Compare collected answers with MuSiQue gold.

    This helper is retained for offline evaluation and tests. The collection
    runner must not use it to control execution.
    """

    if len(terms) != 1:
        return False

    term = terms[0]

    value = term.get("value")

    if not isinstance(value, str):
        return False

    gold_answers = (case.answer, *case.answer_aliases)

    if term.get("type") == "uri":
        expected_iris = {str(entity_iri(candidate)) for candidate in gold_answers}

        return value in expected_iris

    return _normalize_answer(value) in {_normalize_answer(candidate) for candidate in gold_answers}


def display_answer_term(term: SPARQLTerm) -> str:
    """Return a human-readable representation of one collected answer term."""

    value = term.get("value")

    if not isinstance(value, str):
        return repr(term)

    if value.startswith(ENTITY_NAMESPACE):
        return unquote(value[len(ENTITY_NAMESPACE) :])

    return value


def validation_feedback(*, response: str, error: ValueError) -> str:
    """Build mechanical repair feedback after an interface-invalid response."""

    return json.dumps(
        {
            "message": (
                "The previous response could not enter the query execution "
                "interface. Return valid JSON containing matched_triples "
                "and an executable SPARQL query exposing ?answer. "
                "Do not correct the query based on benchmark answer quality."
            ),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "previous_response": response,
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def _result_bindings(result: SPARQLResult) -> tuple[dict[str, object], ...]:
    raw_results = _string_keyed_dict(result.get("results"))

    if raw_results is None:
        return ()

    raw_bindings = raw_results.get("bindings")

    if not isinstance(raw_bindings, list):
        return ()

    bindings: list[dict[str, object]] = []

    for raw_binding in raw_bindings:
        binding = _string_keyed_dict(raw_binding)

        if binding is not None:
            bindings.append(binding)

    return tuple(bindings)


def _string_keyed_dict(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None

    if not all(isinstance(key, str) for key in value):
        return None

    return cast(dict[str, object], value)


def _normalize_answer(text: str) -> str:
    return " ".join(text.split()).casefold()
