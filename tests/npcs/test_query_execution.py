"""Tests for the NPCS and GraphDB query execution path."""

import json

import pytest

from graphragprov.graphdb import GraphDBClient
from graphragprov.npcs import NPCSClient
from graphragprov.query import execute_provenance_query


def test_execute_provenance_query_connects_npcs_and_graphdb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graphdb = GraphDBClient(
        base_url="http://localhost:7200",
        repository="graphragprov",
    )
    npcs = NPCSClient(
        base_url="http://localhost:8082",
    )

    original_query = "SELECT ?answer WHERE { ?s ?p ?answer }"
    rewritten_query = "SELECT ?answer ?finalprovennacevariable WHERE { ?s ?p ?answer }"

    original_result: dict[str, object] = {
        "results": {
            "bindings": [
                {
                    "answer": {
                        "type": "uri",
                        "value": "urn:answer",
                    }
                }
            ]
        }
    }

    rewritten_result: dict[str, object] = {
        "results": {
            "bindings": [
                {
                    "answer": {
                        "type": "uri",
                        "value": "urn:answer",
                    },
                    "finalprovennacevariable": {
                        "type": "literal",
                        "value": "⊕((⊗token,))",
                    },
                }
            ]
        }
    }

    graphdb_queries: list[str] = []

    def fake_graphdb_query(
        self: GraphDBClient,
        sparql: str,
    ) -> dict[str, object]:
        del self
        graphdb_queries.append(sparql)

        if sparql == original_query:
            return original_result

        if sparql == rewritten_query:
            return rewritten_result

        raise AssertionError(f"unexpected query: {sparql}")

    def fake_npcs_rewrite(
        self: NPCSClient,
        sparql: str,
    ) -> str:
        del self
        assert sparql == original_query
        return rewritten_query

    monkeypatch.setattr(
        GraphDBClient,
        "query",
        fake_graphdb_query,
    )
    monkeypatch.setattr(
        NPCSClient,
        "rewrite",
        fake_npcs_rewrite,
    )

    execution = execute_provenance_query(
        sparql=original_query,
        graphdb=graphdb,
        npcs=npcs,
    )

    assert graphdb_queries == [
        original_query,
        rewritten_query,
    ]
    assert execution.original_result == original_result
    assert execution.rewritten_query == rewritten_query
    assert execution.rewritten_result == rewritten_result
    assert json.loads(execution.to_json()) == execution.to_dict()


def test_empty_query_is_rejected() -> None:
    graphdb = GraphDBClient(
        base_url="http://localhost:7200",
        repository="graphragprov",
    )
    npcs = NPCSClient(
        base_url="http://localhost:8082",
    )

    with pytest.raises(
        ValueError,
        match="SPARQL query must not be empty",
    ):
        execute_provenance_query(
            sparql="   ",
            graphdb=graphdb,
            npcs=npcs,
        )
