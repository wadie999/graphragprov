"""Tests for one-shot graph QA-agent execution."""

from __future__ import annotations

import json
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
                "sparql": None,
                "rationale": "The required relation is absent.",
                "assumptions": [],
            }
        ),
    )

    assert len(graphdb_queries) == 1
    assert result.decision.status == "unanswerable"
    assert result.query_attempts == ()


def test_query_decision_executes_and_decodes_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
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
                "sparql": semantic_query,
                "rationale": "The graph contains the direct relation.",
                "assumptions": [],
            }
        ),
    )

    assert result.decision.status == "query"
    assert len(result.query_attempts) == 1

    attempt = result.query_attempts[0]

    assert attempt.provenance_status == "decoded"
    assert len(attempt.answer_provenances) == 1
    assert attempt.answer_provenances[0].polynomial == "polynomial"


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
