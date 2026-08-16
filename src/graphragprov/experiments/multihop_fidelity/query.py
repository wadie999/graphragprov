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
    """Validated evidence selection and semantic SPARQL for one query attempt."""

    matched_triples: tuple[str, ...]
    semantic_sparql: str

    def __post_init__(self) -> None:
        if not self.matched_triples:
            raise ValueError("reference query plan must contain at least one matched triple")

        if not self.semantic_sparql.strip():
            raise ValueError("reference query plan SPARQL must not be empty")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable representation."""

        return {
            "matched_triples": list(self.matched_triples),
            "semantic_sparql": self.semantic_sparql,
        }


@dataclass(frozen=True, slots=True)
class ReferenceQueryGeneration:
    """One provider generation together with its validated reference plan."""

    prompt: str
    response: str
    plan: ReferenceQueryPlan

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable representation."""

        return {"prompt": self.prompt, "response": self.response, "plan": self.plan.to_dict()}


def generate_reference_query(
    *,
    case: MusiqueCase,
    graph_ntriples: str,
    feedback: str | None,
    generate_response: GenerateResponse,
) -> ReferenceQueryGeneration:
    """Generate and deterministically validate one reference query attempt."""

    prompt = build_musique_sparql_prompt(
        case=case, graph_ntriples=graph_ntriples, feedback=feedback
    )

    response = generate_response(prompt)

    plan = parse_reference_query_plan(response, graph_ntriples=graph_ntriples)

    return ReferenceQueryGeneration(prompt=prompt, response=response, plan=plan)


def parse_reference_query_plan(response: str, *, graph_ntriples: str) -> ReferenceQueryPlan:
    """Parse an evidence-first query response against the frozen graph.

    Every selected triple must occur literally in the frozen semantic graph.
    The model therefore selects evidence before compiling it into SPARQL.
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

    if not isinstance(raw_matched, list) or not raw_matched:
        raise ValueError("matched_triples must be a non-empty JSON array")

    matched_items: list[str] = []

    for item in raw_matched:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("every matched_triples item must be a non-empty string")

        matched_items.append(item.strip())

    matched_triples = tuple(matched_items)

    if len(set(matched_triples)) != len(matched_triples):
        raise ValueError("matched_triples must not contain duplicates")

    graph_lines = {line.strip() for line in graph_ntriples.splitlines() if line.strip()}

    missing = tuple(triple for triple in matched_triples if triple not in graph_lines)

    if missing:
        raise ValueError(
            "matched_triples must be copied exactly "
            "from the frozen RDF graph; "
            f"not found: {list(missing)!r}"
        )

    raw_sparql = payload["sparql"]

    if not isinstance(raw_sparql, str) or not raw_sparql.strip():
        raise ValueError("sparql must be a non-empty string")

    semantic_sparql = raw_sparql.strip()

    normalized = " ".join(semantic_sparql.casefold().split())

    # The current NPCS rewrite path does not preserve the final provenance
    # projection correctly for SELECT DISTINCT.
    if "select distinct" in normalized:
        raise ValueError(
            "DISTINCT is not allowed because the current NPCS rewrite path "
            "does not correctly preserve provenance for SELECT DISTINCT"
        )

    if "?answer" not in semantic_sparql:
        raise ValueError("SPARQL must project the final answer as ?answer")

    return ReferenceQueryPlan(matched_triples=matched_triples, semantic_sparql=semantic_sparql)


def compile_reference_query(
    plan: ReferenceQueryPlan, *, scope: QueryScope, support_source_ids: tuple[str, ...]
) -> str:
    """Apply execution scope outside the language-model query policy."""

    if scope is QueryScope.SUPPORT:
        return compile_scoped_select_query(plan.semantic_sparql, source_unit_ids=support_source_ids)

    if scope is QueryScope.REPOSITORY:
        return plan.semantic_sparql

    raise ValueError(f"unsupported query scope: {scope!r}")


def answer_terms(result: SPARQLResult) -> tuple[SPARQLTerm, ...]:
    """Return unique ?answer RDF terms from a SPARQL JSON result.

    SPARQL bag duplicates are collapsed only for benchmark-answer comparison.
    Provenance execution still operates over the actual query.
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
    """Return whether exactly one unique binding matches the benchmark answer."""

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
    """Return a human-readable representation of one answer binding."""

    value = term.get("value")

    if not isinstance(value, str):
        return repr(term)

    if value.startswith(ENTITY_NAMESPACE):
        return unquote(value[len(ENTITY_NAMESPACE) :])

    return value


def validation_feedback(*, response: str, error: ValueError) -> str:
    """Build deterministic feedback after query-response validation failure."""

    return json.dumps(
        {
            "message": (
                "The previous JSON response was rejected by the deterministic "
                "validator. Return exact frozen-graph triples and compile only "
                "those triples into a plain SELECT ?answer query."
            ),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "previous_response": response,
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def execution_feedback(
    *,
    case: MusiqueCase,
    scope: QueryScope,
    plan: ReferenceQueryPlan,
    execution_sparql: str,
    result: SPARQLResult,
    terms: tuple[SPARQLTerm, ...],
) -> str:
    """Build feedback after a valid query returns the wrong answer."""

    return json.dumps(
        {
            "message": (
                "The previous query was executed "
                f"with query_scope={scope.value!r} "
                "and did not return exactly the expected ?answer. "
                "Re-check the evidence selection first, then rebuild SPARQL "
                "only from exact frozen-graph triples. Preserve each selected "
                "triple's subject/predicate/object orientation."
            ),
            "query_scope": scope.value,
            "expected_answer": case.answer,
            "observed_answers": [display_answer_term(term) for term in terms],
            "previous_matched_triples": list(plan.matched_triples),
            "previous_semantic_sparql": (plan.semantic_sparql),
            "previous_execution_sparql": (execution_sparql),
            "graphdb_result": result,
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
