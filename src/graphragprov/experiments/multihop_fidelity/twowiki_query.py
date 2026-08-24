"""Reference query construction for 2WikiMultiHopQA cases."""

from __future__ import annotations

import json
from urllib.parse import unquote

from graphragprov.benchmarks.twowiki.case import TwoWikiCase
from graphragprov.experiments.multihop_fidelity.config import QueryScope
from graphragprov.experiments.multihop_fidelity.query import (
    ReferenceQueryGeneration,
    ReferenceQueryValidationError,
    SPARQLTerm,
    display_answer_term,
    parse_reference_query_plan,
)
from graphragprov.extraction.run import GenerateResponse
from graphragprov.rdf.terms import ENTITY_NAMESPACE, entity_iri

TWOWIKI_QUERY_PROMPT_VERSION = "twowiki-sparql-evidence-first-v1"


WRITE_SPARQL_FOR_TWOWIKI_QUESTION = """
Construct the SPARQL SELECT query that represents the 2WikiMultiHopQA question
over the frozen RDF graph below.

The benchmark evidence relations describe the intended semantic dependency
chain. They are supervision, not RDF statements. The frozen RDF graph is the
only graph that may be queried.

Step 1 — select graph evidence

For every benchmark evidence relation:

1. Locate the exact RDF triple or triples in the frozen graph that represent
   that relation.

2. Copy those RDF triples verbatim into `matched_triples`.

3. Preserve subject, predicate, object, and predicate direction exactly.

Step 2 — compile selected evidence into SPARQL

Build the WHERE clause only from the selected graph evidence.

Keep entities explicitly named by the natural-language question as constants.

Intermediate entities that connect benchmark evidence relations must normally
be represented by shared variables rather than copied as constants from the
benchmark supervision.

Replace the final answer position with `?answer`.

The same intermediate entity must use the same variable wherever it joins
selected triples.

SPARQL requirements:

- project the final result as ?answer;
- derive ?answer from graph patterns;
- use only RDF terms present in the frozen graph;
- include an explicit WHERE clause;
- do not use FROM, GRAPH, SERVICE, or update operations;
- do not manufacture the expected answer using VALUES, BIND, FILTER, or an
  answer constant;
- do not use SELECT DISTINCT;
- preserve the orientation of every selected RDF triple.

Return only one valid JSON object with exactly these fields:

{
  "matched_triples": [
    "<subject> <predicate> <object> ."
  ],
  "sparql": "SELECT ?answer WHERE { ... }"
}

Every item in `matched_triples` must be copied exactly from one complete line
of the frozen RDF graph.
""".strip()


def build_twowiki_sparql_prompt(
    *, case: TwoWikiCase, graph_ntriples: str, feedback: str | None = None
) -> str:
    """Build the evidence-first 2Wiki SPARQL-generation prompt."""

    if case.answer is None:
        raise ValueError("2Wiki query construction requires a gold answer")

    evidence_chain = "\n".join(
        (f"{index}. {evidence.subject} | {evidence.relation} | {evidence.object}")
        for index, evidence in enumerate(case.evidences, start=1)
    )

    parts = [
        "EXPERIMENT TASK — WRITE SPARQL FOR 2WIKI QUESTION",
        f"Prompt version: {TWOWIKI_QUERY_PROMPT_VERSION}",
        WRITE_SPARQL_FOR_TWOWIKI_QUESTION,
        f"Question: {case.question}",
        f"Expected answer: {case.answer}",
        "Benchmark evidence relations:\n" + evidence_chain,
        "Frozen RDF graph:\n" + graph_ntriples,
    ]

    if feedback is not None:
        parts.extend(
            [
                "PREVIOUS QUERY FEEDBACK",
                feedback,
                (
                    "Return a corrected JSON object. "
                    "Re-select matched_triples if necessary, then rebuild "
                    "SPARQL only from exact frozen-graph triples."
                ),
            ]
        )

    return "\n\n".join(parts) + "\n"


def generate_twowiki_reference_query(
    *,
    case: TwoWikiCase,
    graph_ntriples: str,
    feedback: str | None,
    generate_response: GenerateResponse,
) -> ReferenceQueryGeneration:
    """Generate and deterministically validate one 2Wiki query attempt."""

    prompt = build_twowiki_sparql_prompt(
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


def answer_matches_twowiki_case(case: TwoWikiCase, terms: tuple[SPARQLTerm, ...]) -> bool:
    """Return whether one unique binding matches the 2Wiki gold answer."""

    if case.answer is None or len(terms) != 1:
        return False

    term = terms[0]
    value = term.get("value")

    if not isinstance(value, str):
        return False

    if term.get("type") == "uri":
        return value == str(entity_iri(case.answer))

    return _normalize_answer(value) == _normalize_answer(case.answer)


def twowiki_execution_feedback(
    *,
    case: TwoWikiCase,
    scope: QueryScope,
    generation: ReferenceQueryGeneration,
    execution_sparql: str,
    result: dict[str, object],
    terms: tuple[SPARQLTerm, ...],
) -> str:
    """Build deterministic feedback after a wrong ordinary answer."""

    if case.answer is None:
        raise ValueError("2Wiki execution feedback requires a gold answer")

    return json.dumps(
        {
            "message": (
                "The previous query was executed against the real RDF database "
                f"with query_scope={scope.value!r} and did not return exactly "
                "the expected ?answer. Re-check the selected frozen-graph "
                "evidence and the variable joins, then rebuild SPARQL without "
                "changing triple orientation."
            ),
            "query_scope": scope.value,
            "expected_answer": case.answer,
            "observed_answers": [display_answer_term(term) for term in terms],
            "previous_matched_triples": list(generation.plan.matched_triples),
            "previous_semantic_sparql": (generation.plan.semantic_sparql),
            "previous_execution_sparql": execution_sparql,
            "graphdb_result": result,
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def _normalize_answer(text: str) -> str:
    if text.startswith(ENTITY_NAMESPACE):
        text = unquote(text[len(ENTITY_NAMESPACE) :])

    return " ".join(text.split()).casefold()
