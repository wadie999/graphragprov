"""Tests for reference query construction."""

from __future__ import annotations

import json

import pytest

from graphragprov.benchmarks.musique import (
    MusiqueCase,
    MusiqueHop,
    MusiqueParagraph,
    collect_musique_source_units,
)
from graphragprov.experiments.multihop_fidelity.config import QueryScope
from graphragprov.experiments.multihop_fidelity.query import (
    ReferenceQueryPlan,
    ReferenceQueryValidationError,
    SPARQLTerm,
    answer_matches_case,
    answer_terms,
    compile_reference_query,
    execution_feedback,
    generate_reference_query,
    parse_reference_query_plan,
    validation_feedback,
)
from graphragprov.rdf.terms import entity_iri, unit_graph_iri

PERFORMER_TRIPLE = (
    "<urn:graphragprov:entity:Album%20Alpha> "
    "<urn:graphragprov:predicate:performer> "
    "<urn:graphragprov:entity:Artist%20Beta> ."
)

BIRTH_TRIPLE = (
    "<urn:graphragprov:entity:Artist%20Beta> "
    "<urn:graphragprov:predicate:placeOfBirth> "
    "<urn:graphragprov:entity:City%20Gamma> ."
)

GRAPH_NTRIPLES = "\n".join((PERFORMER_TRIPLE, BIRTH_TRIPLE))

SEMANTIC_SPARQL = (
    "SELECT ?answer WHERE {\n"
    "  <urn:graphragprov:entity:Album%20Alpha> "
    "<urn:graphragprov:predicate:performer> ?performer .\n"
    "  ?performer "
    "<urn:graphragprov:predicate:placeOfBirth> ?answer .\n"
    "}"
)


def _case() -> MusiqueCase:
    return MusiqueCase(
        case_id="2hop__query_test",
        question="Where was the performer of Album Alpha born?",
        answer="City Gamma",
        answer_aliases=("Gamma City",),
        answerable=True,
        paragraphs=(
            MusiqueParagraph(
                index=2, title="Artist Beta", text="Artist Beta was born in City Gamma."
            ),
            MusiqueParagraph(
                index=7, title="Album Alpha", text="Album Alpha was performed by Artist Beta."
            ),
        ),
        decomposition=(
            MusiqueHop(
                hop_id=0,
                question="Album Alpha >> performer",
                answer="Artist Beta",
                paragraph_support_index=7,
            ),
            MusiqueHop(
                hop_id=1,
                question="#1 >> place of birth",
                answer="City Gamma",
                paragraph_support_index=2,
            ),
        ),
        gold_support_indices=(7, 2),
    )


def _valid_response() -> str:
    return json.dumps(
        {"matched_triples": [PERFORMER_TRIPLE, BIRTH_TRIPLE], "sparql": SEMANTIC_SPARQL}
    )


def test_generate_reference_query_uses_real_prompt_builder_and_validates_plan() -> None:
    case = _case()

    prompts: list[str] = []

    def generate(prompt: str) -> str:
        prompts.append(prompt)

        assert case.question in prompt
        assert PERFORMER_TRIPLE in prompt
        assert BIRTH_TRIPLE in prompt

        return _valid_response()

    generation = generate_reference_query(
        case=case, graph_ntriples=GRAPH_NTRIPLES, feedback=None, generate_response=generate
    )

    assert len(prompts) == 1
    assert generation.prompt == prompts[0]
    assert generation.response == _valid_response()

    assert generation.plan.matched_triples == (PERFORMER_TRIPLE, BIRTH_TRIPLE)

    assert generation.plan.semantic_sparql == SEMANTIC_SPARQL


def test_generate_reference_query_preserves_rejected_paid_response() -> None:
    case = _case()

    invalid_response = json.dumps(
        {
            "matched_triples": [
                (
                    "<urn:graphragprov:entity:Artist%20Beta> "
                    "<urn:graphragprov:predicate:livesIn> "
                    "<urn:graphragprov:entity:City%20Gamma> ."
                )
            ],
            "sparql": SEMANTIC_SPARQL,
        }
    )

    prompts: list[str] = []

    def generate(prompt: str) -> str:
        prompts.append(prompt)
        return invalid_response

    with pytest.raises(ReferenceQueryValidationError, match="not found") as caught:
        generate_reference_query(
            case=case, graph_ntriples=GRAPH_NTRIPLES, feedback=None, generate_response=generate
        )

    error = caught.value

    assert len(prompts) == 1
    assert error.prompt == prompts[0]
    assert error.response == invalid_response
    assert isinstance(error.validation_error, ValueError)
    assert "not found" in str(error.validation_error)


def test_reference_query_rejects_triple_not_present_in_frozen_graph() -> None:
    hallucinated = (
        "<urn:graphragprov:entity:Artist%20Beta> "
        "<urn:graphragprov:predicate:livesIn> "
        "<urn:graphragprov:entity:City%20Gamma> ."
    )

    response = json.dumps(
        {"matched_triples": [PERFORMER_TRIPLE, hallucinated], "sparql": SEMANTIC_SPARQL}
    )

    with pytest.raises(ValueError, match="not found"):
        parse_reference_query_plan(response, graph_ntriples=GRAPH_NTRIPLES)


def test_reference_query_requires_literal_frozen_graph_evidence() -> None:
    reversed_triple = (
        "<urn:graphragprov:entity:Artist%20Beta> "
        "<urn:graphragprov:predicate:performer> "
        "<urn:graphragprov:entity:Album%20Alpha> ."
    )

    response = json.dumps({"matched_triples": [reversed_triple], "sparql": SEMANTIC_SPARQL})

    with pytest.raises(ValueError, match="not found"):
        parse_reference_query_plan(response, graph_ntriples=GRAPH_NTRIPLES)


def test_reference_query_rejects_duplicate_matched_triples() -> None:
    response = json.dumps(
        {"matched_triples": [PERFORMER_TRIPLE, PERFORMER_TRIPLE], "sparql": SEMANTIC_SPARQL}
    )

    with pytest.raises(ValueError, match="must not contain duplicates"):
        parse_reference_query_plan(response, graph_ntriples=GRAPH_NTRIPLES)


def test_reference_query_rejects_select_distinct_for_current_npcs_path() -> None:
    response = json.dumps(
        {
            "matched_triples": [PERFORMER_TRIPLE, BIRTH_TRIPLE],
            "sparql": ("SELECT DISTINCT ?answer WHERE { ?subject ?predicate ?answer . }"),
        }
    )

    with pytest.raises(ValueError, match="DISTINCT is not allowed"):
        parse_reference_query_plan(response, graph_ntriples=GRAPH_NTRIPLES)


def test_reference_query_requires_answer_projection() -> None:
    response = json.dumps(
        {
            "matched_triples": [PERFORMER_TRIPLE, BIRTH_TRIPLE],
            "sparql": (
                "SELECT ?city WHERE { ?person <urn:graphragprov:predicate:placeOfBirth> ?city . }"
            ),
        }
    )

    with pytest.raises(ValueError, match=r"\?answer"):
        parse_reference_query_plan(response, graph_ntriples=GRAPH_NTRIPLES)


def test_support_scope_is_applied_by_python_after_semantic_generation() -> None:
    case = _case()
    sources = collect_musique_source_units((case,))

    source_by_title = {source.title: source for source in sources}

    support_source_ids = (
        source_by_title["Album Alpha"].unit_id,
        source_by_title["Artist Beta"].unit_id,
    )

    plan = ReferenceQueryPlan(
        matched_triples=(PERFORMER_TRIPLE, BIRTH_TRIPLE), semantic_sparql=SEMANTIC_SPARQL
    )

    execution_sparql = compile_reference_query(
        plan, scope=QueryScope.SUPPORT, support_source_ids=support_source_ids
    )

    assert execution_sparql != SEMANTIC_SPARQL

    for source_id in support_source_ids:
        graph_iri = str(unit_graph_iri(source_id))

        assert f"FROM <{graph_iri}>" in execution_sparql

    assert "?answer" in execution_sparql


def test_repository_scope_preserves_semantic_query_exactly() -> None:
    plan = ReferenceQueryPlan(
        matched_triples=(PERFORMER_TRIPLE, BIRTH_TRIPLE), semantic_sparql=SEMANTIC_SPARQL
    )

    execution_sparql = compile_reference_query(
        plan, scope=QueryScope.REPOSITORY, support_source_ids=("unused",)
    )

    assert execution_sparql == SEMANTIC_SPARQL


def test_answer_terms_collapse_bag_duplicates_for_answer_evaluation() -> None:
    city_iri = str(entity_iri("City Gamma"))

    result: dict[str, object] = {
        "head": {"vars": ["answer"]},
        "results": {
            "bindings": [
                {"answer": {"type": "uri", "value": city_iri}},
                {"answer": {"type": "uri", "value": city_iri}},
            ]
        },
    }

    terms = answer_terms(result)

    assert len(terms) == 1
    assert terms[0]["value"] == city_iri


def test_answer_matching_uses_entity_iri_construction() -> None:
    case = _case()

    terms: tuple[SPARQLTerm, ...] = ({"type": "uri", "value": str(entity_iri("City Gamma"))},)

    assert answer_matches_case(case, terms)


def test_answer_matching_accepts_normalized_alias_literal() -> None:
    case = _case()

    terms: tuple[SPARQLTerm, ...] = ({"type": "literal", "value": "  GAMMA   CITY "},)

    assert answer_matches_case(case, terms)


def test_answer_matching_rejects_multiple_unique_answers() -> None:
    case = _case()

    terms: tuple[SPARQLTerm, ...] = (
        {"type": "literal", "value": "City Gamma"},
        {"type": "literal", "value": "Other City"},
    )

    assert not answer_matches_case(case, terms)


def test_validation_feedback_preserves_exact_failed_response() -> None:
    response = '{"matched_triples": []}'

    error = ValueError("matched_triples must be non-empty")

    feedback = validation_feedback(response=response, error=error)

    payload = json.loads(feedback)

    assert payload["previous_response"] == response

    assert payload["error_message"] == str(error)

    assert "deterministic validator" in payload["message"]


def test_execution_feedback_records_real_query_and_observed_answer() -> None:
    case = _case()

    plan = ReferenceQueryPlan(
        matched_triples=(PERFORMER_TRIPLE, BIRTH_TRIPLE), semantic_sparql=SEMANTIC_SPARQL
    )

    result: dict[str, object] = {
        "head": {"vars": ["answer"]},
        "results": {"bindings": [{"answer": {"type": "literal", "value": "Wrong City"}}]},
    }

    terms = answer_terms(result)

    feedback = execution_feedback(
        case=case,
        scope=QueryScope.SUPPORT,
        plan=plan,
        execution_sparql="SCOPED QUERY",
        result=result,
        terms=terms,
    )

    payload = json.loads(feedback)

    assert payload["expected_answer"] == "City Gamma"

    assert payload["observed_answers"] == ["Wrong City"]

    assert payload["query_scope"] == "support"

    assert payload["previous_matched_triples"] == [PERFORMER_TRIPLE, BIRTH_TRIPLE]

    assert payload["previous_semantic_sparql"] == SEMANTIC_SPARQL

    assert payload["previous_execution_sparql"] == "SCOPED QUERY"

    assert payload["graphdb_result"] == result
