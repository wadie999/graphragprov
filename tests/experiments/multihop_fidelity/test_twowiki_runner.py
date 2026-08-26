"""Integration-style tests for the 2Wiki H0 runner wrapper."""

from __future__ import annotations

import json
from typing import cast
from unittest.mock import Mock

from graphragprov.benchmarks.twowiki.case import TwoWikiCase, TwoWikiSupportingFact
from graphragprov.benchmarks.twowiki.evidence import TwoWikiEvidence
from graphragprov.benchmarks.twowiki.materialization import collect_twowiki_source_units
from graphragprov.benchmarks.twowiki.paragraph import TwoWikiParagraph
from graphragprov.experiments.multihop_fidelity.config import (
    ArtifactOrigin,
    ExperimentConfig,
    QueryScope,
)
from graphragprov.experiments.multihop_fidelity.runner import H0CaseResult, run_twowiki_h0_case
from graphragprov.experiments.multihop_fidelity.telemetry import ExperimentTelemetryRecorder
from graphragprov.extraction import parse_extraction_response
from graphragprov.graphdb import GraphDBClient
from graphragprov.npcs import NPCSClient
from graphragprov.query import PROVENANCE_VARIABLE
from graphragprov.rdf.provenance import occurrence_token
from graphragprov.rdf.terms import entity_iri, predicate_iri, unit_graph_iri


def _case() -> TwoWikiCase:
    return TwoWikiCase(
        case_id="twowiki-runner-test",
        question_type="compositional",
        question="Where was the director of film The Fascist born?",
        paragraphs=(
            TwoWikiParagraph(
                index=0, title="Distractor", sentences=("This paragraph is irrelevant.",)
            ),
            TwoWikiParagraph(
                index=1,
                title="The Fascist",
                sentences=("The Fascist is a film directed by Luciano Salce.",),
            ),
            TwoWikiParagraph(
                index=2, title="Luciano Salce", sentences=("Luciano Salce was born in Rome.",)
            ),
        ),
        supporting_facts=(
            TwoWikiSupportingFact(title="The Fascist", sentence_index=0),
            TwoWikiSupportingFact(title="Luciano Salce", sentence_index=0),
        ),
        evidences=(
            TwoWikiEvidence(subject="The Fascist", relation="director", object="Luciano Salce"),
            TwoWikiEvidence(subject="Luciano Salce", relation="place of birth", object="Rome"),
        ),
        evidence_ids=None,
        answer="Rome",
        answer_id=None,
        entity_ids=(),
    )


def _configuration() -> ExperimentConfig:
    return ExperimentConfig(
        graph_origin=ArtifactOrigin.REFERENCE,
        query_origin=ArtifactOrigin.REFERENCE,
        query_scope=QueryScope.SUPPORT,
        max_source_attempts=2,
        max_query_attempts=3,
    )


def _grounded_value(value: str, *, segment: str, quote: str) -> dict[str, object]:
    return {"value": value, "evidence": [{"segment": segment, "quote": quote, "occurrence": 1}]}


def _fascist_response() -> str:
    return json.dumps(
        {
            "statements": [
                {
                    "subject": _grounded_value("The Fascist", segment="title", quote="The Fascist"),
                    "predicate": _grounded_value("director", segment="text", quote="directed by"),
                    "object": _grounded_value(
                        "Luciano Salce", segment="text", quote="Luciano Salce"
                    ),
                }
            ]
        }
    )


def _salce_response() -> str:
    return json.dumps(
        {
            "statements": [
                {
                    "subject": _grounded_value(
                        "Luciano Salce", segment="title", quote="Luciano Salce"
                    ),
                    "predicate": _grounded_value("placeOfBirth", segment="text", quote="born in"),
                    "object": _grounded_value("Rome", segment="text", quote="Rome"),
                }
            ]
        }
    )


def _graph_generator(prompt: str) -> str:
    if "The Fascist is a film directed by Luciano Salce." in prompt:
        return _fascist_response()

    if "Luciano Salce was born in Rome." in prompt:
        return _salce_response()

    raise AssertionError(f"unexpected graph prompt:\n{prompt}")


def _semantic_triples() -> tuple[str, str]:
    director = (
        f"{entity_iri('The Fascist').n3()} "
        f"{predicate_iri('director').n3()} "
        f"{entity_iri('Luciano Salce').n3()} ."
    )

    birth = (
        f"{entity_iri('Luciano Salce').n3()} "
        f"{predicate_iri('placeOfBirth').n3()} "
        f"{entity_iri('Rome').n3()} ."
    )

    return director, birth


def _valid_query_response() -> str:
    director, birth = _semantic_triples()

    semantic_sparql = (
        "SELECT ?answer WHERE {\n"
        f"  {entity_iri('The Fascist').n3()} "
        f"{predicate_iri('director').n3()} ?director .\n"
        f"  ?director {predicate_iri('placeOfBirth').n3()} ?answer .\n"
        "}"
    )

    return json.dumps({"matched_triples": [director, birth], "sparql": semantic_sparql})


def _observation_result(case: TwoWikiCase) -> dict[str, object]:
    sources = collect_twowiki_source_units((case,))
    by_title = {source.title: source for source in sources}

    return {
        "head": {"vars": ["graph", "subject", "predicate", "object"]},
        "results": {
            "bindings": [
                {
                    "graph": {
                        "type": "uri",
                        "value": str(unit_graph_iri(by_title["The Fascist"].unit_id)),
                    },
                    "subject": {"type": "uri", "value": str(entity_iri("The Fascist"))},
                    "predicate": {"type": "uri", "value": str(predicate_iri("director"))},
                    "object": {"type": "uri", "value": str(entity_iri("Luciano Salce"))},
                },
                {
                    "graph": {
                        "type": "uri",
                        "value": str(unit_graph_iri(by_title["Luciano Salce"].unit_id)),
                    },
                    "subject": {"type": "uri", "value": str(entity_iri("Luciano Salce"))},
                    "predicate": {"type": "uri", "value": str(predicate_iri("placeOfBirth"))},
                    "object": {"type": "uri", "value": str(entity_iri("Rome"))},
                },
            ]
        },
    }


def _provenance_polynomial(case: TwoWikiCase) -> str:
    sources = collect_twowiki_source_units((case,))
    by_title = {source.title: source for source in sources}

    fascist = by_title["The Fascist"]
    salce = by_title["Luciano Salce"]

    fascist_extraction = parse_extraction_response(fascist, _fascist_response())
    salce_extraction = parse_extraction_response(salce, _salce_response())

    tokens = sorted(
        (
            occurrence_token(unit_id=fascist.unit_id, statement=fascist_extraction.statements[0]),
            occurrence_token(unit_id=salce.unit_id, statement=salce_extraction.statements[0]),
        )
    )

    return "⊕((⊗" + ",".join(tokens) + ",))"


def _clients(case: TwoWikiCase) -> tuple[Mock, Mock]:
    graphdb = Mock(spec=GraphDBClient)
    npcs = Mock(spec=NPCSClient)

    npcs.rewrite.return_value = "REWRITTEN PROVENANCE QUERY"

    def query(sparql: str) -> dict[str, object]:
        if "SELECT DISTINCT ?graph ?subject ?predicate ?object" in sparql:
            return _observation_result(case)

        if sparql == "REWRITTEN PROVENANCE QUERY":
            return {
                "head": {"vars": ["answer", PROVENANCE_VARIABLE]},
                "results": {
                    "bindings": [
                        {
                            "answer": {"type": "uri", "value": str(entity_iri("Rome"))},
                            PROVENANCE_VARIABLE: {
                                "type": "literal",
                                "value": _provenance_polynomial(case),
                            },
                        }
                    ]
                },
            }

        if "?answer" in sparql:
            return {
                "head": {"vars": ["answer"]},
                "results": {
                    "bindings": [{"answer": {"type": "uri", "value": str(entity_iri("Rome"))}}]
                },
            }

        raise AssertionError(f"unexpected GraphDB query:\n{sparql}")

    graphdb.query.side_effect = query

    return graphdb, npcs


def test_twowiki_runner_uses_shared_complete_h0_lifecycle() -> None:
    case = _case()
    sources = collect_twowiki_source_units((case,))
    graphdb, npcs = _clients(case)

    query_calls = 0

    def query_generate(prompt: str) -> str:
        nonlocal query_calls
        query_calls += 1

        assert case.question in prompt

        return _valid_query_response()

    outcome = run_twowiki_h0_case(
        case=case,
        sources=sources,
        configuration=_configuration(),
        graph_generate_response=_graph_generator,
        query_generate_response=query_generate,
        graphdb=cast(GraphDBClient, graphdb),
        npcs=cast(NPCSClient, npcs),
        telemetry=ExperimentTelemetryRecorder(),
    )

    assert isinstance(outcome, H0CaseResult)

    assert outcome.case_id == case.case_id
    assert outcome.hop_count == 2
    assert outcome.support_source_ids == (sources[1].unit_id, sources[2].unit_id)

    assert outcome.extraction_measurements.statement_occurrence_count == 2
    assert outcome.graph_measurements.semantic_triple_count == 2

    assert len(outcome.query_attempts) == 1
    assert outcome.query_attempts[0].observed_answers == ("Rome",)

    assert outcome.final_provenance.provenance_status == "decoded"

    assert query_calls == 1
    assert graphdb.update.call_count == 2
    assert graphdb.upload_trig_star.call_count == 2

    stage_names = {stage.stage for stage in outcome.telemetry.stages}

    assert {
        "graph.reference.extraction",
        "graph.reference.measurements",
        "graph.clear_support",
        "graph.materialization",
        "graph.observation",
        "graph.frozen.measurements",
        "query.reference.generation",
        "graphdb.semantic",
        "provenance.execution",
    } <= stage_names
