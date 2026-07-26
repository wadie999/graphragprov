"""Tests for multi-turn graph QA-agent execution."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import cast

import pytest

from graphragprov.graphdb import GraphDBClient
from graphragprov.npcs import NPCSClient
from graphragprov.provenance import DecodedProvenance, SourceRegistry
from graphragprov.qaagent import QAAgentConfiguration, run_tuple_qa_agent
from graphragprov.rdf.terms import unit_graph_iri

UNIT_ID = "u_" + "a" * 64
GRAPH_IRI = str(unit_graph_iri(UNIT_ID))


class _DecodedStub:
    def to_dict(self) -> dict[str, object]:
        return {"derivations": [{"occurrences": [{"token": "token"}]}]}


def test_unanswerable_decision_executes_no_answer_query(monkeypatch: pytest.MonkeyPatch) -> None:
    graphdb = _graphdb()
    npcs = _npcs()

    graphdb_queries: list[str] = []

    def fake_query(self: GraphDBClient, sparql: str) -> dict[str, object]:
        del self

        graphdb_queries.append(sparql)

        return _observation_result()

    monkeypatch.setattr(GraphDBClient, "query", fake_query)

    result = run_tuple_qa_agent(
        question="Who designed it?",
        hop_count=2,
        configuration=QAAgentConfiguration(),
        source_unit_ids=(UNIT_ID,),
        graphdb=graphdb,
        npcs=npcs,
        registry=SourceRegistry(()),
        generate_response=lambda prompt: json.dumps(
            {
                "status": "unanswerable",
                "purpose": None,
                "sparql": None,
                "rationale": "The required relation is absent.",
                "assumptions": [],
            }
        ),
    )

    assert len(graphdb_queries) == 1
    assert result.decision.status == "unanswerable"
    assert result.query_attempts == ()
    assert result.termination_reason == "agent_decision"


def test_final_query_executes_and_decodes_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    graphdb = _graphdb()
    npcs = _npcs()

    semantic_query = (
        "SELECT DISTINCT ?answer "
        "WHERE { "
        "<urn:entity:building> "
        "<urn:predicate:designedBy> "
        "?answer . "
        "}"
    )

    rewritten_query = "SELECT DISTINCT ?answer ?finalprovennacevariable WHERE { ?s ?p ?answer }"

    def fake_query(self: GraphDBClient, sparql: str) -> dict[str, object]:
        del self

        if "SELECT DISTINCT ?graph" in sparql:
            return _observation_result()

        if sparql == rewritten_query:
            return {
                "results": {
                    "bindings": [
                        {
                            "answer": {"type": "uri", "value": "urn:entity:architect"},
                            "finalprovennacevariable": {"type": "literal", "value": "polynomial"},
                        }
                    ]
                }
            }

        assert f"FROM <{GRAPH_IRI}>" in sparql

        return {
            "results": {"bindings": [{"answer": {"type": "uri", "value": "urn:entity:architect"}}]}
        }

    def fake_rewrite(self: NPCSClient, sparql: str) -> str:
        del self

        assert f"FROM <{GRAPH_IRI}>" in sparql

        return rewritten_query

    def fake_decode(value: str, *, registry: SourceRegistry) -> DecodedProvenance:
        del registry

        assert value == "polynomial"

        return cast(DecodedProvenance, _DecodedStub())

    monkeypatch.setattr(GraphDBClient, "query", fake_query)
    monkeypatch.setattr(NPCSClient, "rewrite", fake_rewrite)
    monkeypatch.setattr("graphragprov.qaagent.run.decode_provenance_polynomial", fake_decode)

    result = run_tuple_qa_agent(
        question="Who designed it?",
        hop_count=2,
        configuration=QAAgentConfiguration(),
        source_unit_ids=(UNIT_ID,),
        graphdb=graphdb,
        npcs=npcs,
        registry=SourceRegistry(()),
        generate_response=lambda prompt: json.dumps(
            {
                "status": "query",
                "purpose": "final",
                "sparql": semantic_query,
                "rationale": "The graph contains the direct relation.",
                "assumptions": [],
            }
        ),
    )

    assert result.decision.status == "query"
    assert result.termination_reason == "final_answer"
    assert len(result.query_attempts) == 1

    attempt = result.query_attempts[0]

    assert attempt.purpose == "final"
    assert attempt.provenance_status == "decoded"
    assert len(attempt.answer_provenances) == 1
    assert attempt.answer_provenances[0].polynomial == "polynomial"


def test_inspection_query_is_provenance_decoded_before_final_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graphdb = _graphdb()
    npcs = _npcs()

    inspection_query = "SELECT DISTINCT ?entity WHERE { ?entity ?predicate ?object . }"

    final_query = (
        "SELECT DISTINCT ?answer "
        "WHERE { "
        "<urn:entity:building> "
        "<urn:predicate:designedBy> "
        "?answer . "
        "}"
    )

    generated_responses: Iterator[str] = iter(
        [
            json.dumps(
                {
                    "status": "query",
                    "purpose": "inspection",
                    "sparql": inspection_query,
                    "rationale": "Inspect available entities first.",
                    "assumptions": [],
                }
            ),
            json.dumps(
                {
                    "status": "query",
                    "purpose": "final",
                    "sparql": final_query,
                    "rationale": "The inspection exposed the direct relation.",
                    "assumptions": [],
                }
            ),
        ]
    )

    rewritten_queries = ["REWRITTEN INSPECTION", "REWRITTEN FINAL"]

    rewrite_count = 0

    def fake_generate_response(prompt: str) -> str:
        assert prompt.strip()

        return next(generated_responses)

    def fake_rewrite(self: NPCSClient, sparql: str) -> str:
        nonlocal rewrite_count

        del self

        assert f"FROM <{GRAPH_IRI}>" in sparql

        rewritten_query = rewritten_queries[rewrite_count]
        rewrite_count += 1

        return rewritten_query

    def fake_query(self: GraphDBClient, sparql: str) -> dict[str, object]:
        del self

        if "SELECT DISTINCT ?graph" in sparql:
            return _observation_result()

        if sparql == rewritten_queries[0]:
            return {
                "results": {
                    "bindings": [
                        {
                            "entity": {"type": "uri", "value": "urn:entity:building"},
                            "finalprovennacevariable": {
                                "type": "literal",
                                "value": "inspection-polynomial",
                            },
                        }
                    ]
                }
            }

        if sparql == rewritten_queries[1]:
            return {
                "results": {
                    "bindings": [
                        {
                            "answer": {"type": "uri", "value": "urn:entity:architect"},
                            "finalprovennacevariable": {
                                "type": "literal",
                                "value": "final-polynomial",
                            },
                        }
                    ]
                }
            }

        assert f"FROM <{GRAPH_IRI}>" in sparql

        if "?entity" in sparql:
            return {
                "results": {
                    "bindings": [{"entity": {"type": "uri", "value": "urn:entity:building"}}]
                }
            }

        return {
            "results": {"bindings": [{"answer": {"type": "uri", "value": "urn:entity:architect"}}]}
        }

    decoded_polynomials: list[str] = []

    def fake_decode(value: str, *, registry: SourceRegistry) -> DecodedProvenance:
        del registry

        decoded_polynomials.append(value)

        return cast(DecodedProvenance, _DecodedStub())

    events: list[dict[str, object]] = []

    monkeypatch.setattr(GraphDBClient, "query", fake_query)
    monkeypatch.setattr(NPCSClient, "rewrite", fake_rewrite)
    monkeypatch.setattr("graphragprov.qaagent.run.decode_provenance_polynomial", fake_decode)

    result = run_tuple_qa_agent(
        question="Who designed it?",
        hop_count=2,
        configuration=QAAgentConfiguration(max_turns=2),
        source_unit_ids=(UNIT_ID,),
        graphdb=graphdb,
        npcs=npcs,
        registry=SourceRegistry(()),
        generate_response=fake_generate_response,
        event_sink=events.append,
    )

    assert rewrite_count == 2

    assert decoded_polynomials == ["inspection-polynomial", "final-polynomial"]

    assert result.termination_reason == "final_answer"
    assert len(result.query_attempts) == 2

    inspection_attempt, final_attempt = result.query_attempts

    assert inspection_attempt.purpose == "inspection"
    assert inspection_attempt.provenance_status == "decoded"
    assert inspection_attempt.answer_provenances[0].polynomial == ("inspection-polynomial")

    assert final_attempt.purpose == "final"
    assert final_attempt.provenance_status == "decoded"
    assert final_attempt.answer_provenances[0].polynomial == ("final-polynomial")

    event_types = [event["type"] for event in events]

    assert event_types.count("turn.query.original_completed") == 2
    assert event_types.count("turn.query.rewritten") == 2
    assert event_types.count("turn.query.rewritten_completed") == 2
    assert event_types.count("turn.completed") == 2
    assert event_types[-1] == "run.completed"


def _graphdb() -> GraphDBClient:
    return GraphDBClient(base_url="http://localhost:7200", repository="graphragprov")


def _npcs() -> NPCSClient:
    return NPCSClient(base_url="http://localhost:8082")


def _observation_result() -> dict[str, object]:
    return {
        "results": {
            "bindings": [
                {
                    "graph": {"type": "uri", "value": GRAPH_IRI},
                    "subject": {"type": "uri", "value": "urn:entity:building"},
                    "predicate": {"type": "uri", "value": "urn:predicate:designedBy"},
                    "object": {"type": "uri", "value": "urn:entity:architect"},
                }
            ]
        }
    }
