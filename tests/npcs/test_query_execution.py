"""Tests for the NPCS and GraphDB query execution path."""

import json

import pytest

from graphragprov.graphdb import GraphDBClient
from graphragprov.npcs import NPCSClient
from graphragprov.query import execute_provenance_query
from graphragprov.query.execution import (
    PROVENANCE_VARIABLE,
    ProvenanceQueryExecution,
    extract_provenance_polynomial,
)


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
                    PROVENANCE_VARIABLE: {
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
    assert extract_provenance_polynomial(execution) == "⊕((⊗token,))"
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


@pytest.mark.parametrize(
    "bindings",
    [
        [],
        [
            {PROVENANCE_VARIABLE: {"value": "first"}},
            {PROVENANCE_VARIABLE: {"value": "second"}},
        ],
    ],
)
def test_polynomial_requires_exactly_one_binding(
    bindings: list[dict[str, object]],
) -> None:
    execution = _execution_with_bindings(bindings)

    with pytest.raises(
        ValueError,
        match="exactly one binding",
    ):
        extract_provenance_polynomial(execution)


def test_polynomial_binding_is_required() -> None:
    execution = _execution_with_bindings([{"answer": {"value": "urn:answer"}}])

    with pytest.raises(
        ValueError,
        match=PROVENANCE_VARIABLE,
    ):
        extract_provenance_polynomial(execution)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        42,
        None,
    ],
)
def test_polynomial_must_be_non_empty_string(
    value: object,
) -> None:
    execution = _execution_with_bindings([{PROVENANCE_VARIABLE: {"value": value}}])

    with pytest.raises(
        ValueError,
        match="non-empty string",
    ):
        extract_provenance_polynomial(execution)


def _execution_with_bindings(
    bindings: list[dict[str, object]],
) -> ProvenanceQueryExecution:
    return ProvenanceQueryExecution(
        original_query="SELECT ?answer WHERE {}",
        original_result={
            "results": {
                "bindings": [],
            }
        },
        rewritten_query=("SELECT ?answer ?finalprovennacevariable WHERE {}"),
        rewritten_result={
            "results": {
                "bindings": bindings,
            }
        },
    )
