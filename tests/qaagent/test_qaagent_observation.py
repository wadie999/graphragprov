"""Tests for semantic GraphDB observation by QA agents."""

import pytest

from graphragprov.qaagent import build_semantic_triple_observation_query, observe_semantic_triples
from graphragprov.rdf.terms import unit_graph_iri

UNIT_A = "u_" + "a" * 64
UNIT_B = "u_" + "b" * 64

GRAPH_A = str(unit_graph_iri(UNIT_A))

GRAPH_B = str(unit_graph_iri(UNIT_B))


class FakeQueryExecutor:
    def __init__(self, result: dict[str, object]) -> None:
        self.result = result
        self.queries: list[str] = []

    def query(self, sparql: str) -> dict[str, object]:
        self.queries.append(sparql)

        return self.result


def test_observation_query_uses_sorted_unique_graphs() -> None:
    query = build_semantic_triple_observation_query(source_unit_ids=(UNIT_B, UNIT_A, UNIT_B))

    assert query == (
        "SELECT DISTINCT "
        "?graph ?subject ?predicate ?object\n"
        "WHERE {\n"
        "  VALUES ?graph {\n"
        f"    <{GRAPH_A}>\n"
        f"    <{GRAPH_B}>\n"
        "  }\n"
        "  GRAPH ?graph {\n"
        "    ?subject ?predicate ?object .\n"
        "    FILTER(isIRI(?subject))\n"
        "  }\n"
        "}\n"
        "ORDER BY "
        "?graph ?subject ?predicate ?object"
    )


def test_repository_observation_has_no_values_scope() -> None:
    query = build_semantic_triple_observation_query(source_unit_ids=None)

    assert "VALUES ?graph" not in query
    assert "GRAPH ?graph" in query
    assert "FILTER(isIRI(?subject))" in query


def test_observation_requires_source_units_when_scoped() -> None:
    with pytest.raises(ValueError, match="at least one source unit"):
        build_semantic_triple_observation_query(source_unit_ids=())


def test_semantic_triples_are_parsed_and_sorted() -> None:
    result: dict[str, object] = {
        "results": {
            "bindings": [
                {
                    "graph": {"type": "uri", "value": GRAPH_B},
                    "subject": {"type": "uri", "value": "urn:subject:b"},
                    "predicate": {"type": "uri", "value": "urn:predicate:b"},
                    "object": {
                        "type": "literal",
                        "value": "42",
                        "datatype": ("http://www.w3.org/2001/XMLSchema#integer"),
                    },
                },
                {
                    "graph": {"type": "uri", "value": GRAPH_A},
                    "subject": {"type": "uri", "value": "urn:subject:a"},
                    "predicate": {"type": "uri", "value": "urn:predicate:a"},
                    "object": {"type": "uri", "value": "urn:object:a"},
                },
            ]
        }
    }

    graphdb = FakeQueryExecutor(result)

    observation = observe_semantic_triples(graphdb=graphdb, source_unit_ids=(UNIT_B, UNIT_A))

    assert graphdb.queries == [observation.query]

    assert observation.graph_iris == (GRAPH_A, GRAPH_B)

    assert tuple(triple.to_nquad() for triple in observation.triples) == (
        (f"<urn:subject:a> <urn:predicate:a> <urn:object:a> <{GRAPH_A}> ."),
        (
            "<urn:subject:b> "
            "<urn:predicate:b> "
            '"42"^^'
            "<http://www.w3.org/"
            "2001/XMLSchema#integer> "
            f"<{GRAPH_B}> ."
        ),
    )


def test_duplicate_bindings_are_removed() -> None:
    binding = {
        "graph": {"type": "uri", "value": GRAPH_A},
        "subject": {"type": "uri", "value": "urn:subject"},
        "predicate": {"type": "uri", "value": "urn:predicate"},
        "object": {"type": "literal", "value": "value"},
    }

    graphdb = FakeQueryExecutor({"results": {"bindings": [binding, binding]}})

    observation = observe_semantic_triples(graphdb=graphdb, source_unit_ids=(UNIT_A,))

    assert len(observation.triples) == 1


def test_invalid_object_type_is_rejected() -> None:
    graphdb = FakeQueryExecutor(
        {
            "results": {
                "bindings": [
                    {
                        "graph": {"type": "uri", "value": GRAPH_A},
                        "subject": {"type": "uri", "value": "urn:subject"},
                        "predicate": {"type": "uri", "value": "urn:predicate"},
                        "object": {"type": "bnode", "value": "node"},
                    }
                ]
            }
        }
    )

    with pytest.raises(ValueError, match="URI or literal"):
        observe_semantic_triples(graphdb=graphdb, source_unit_ids=(UNIT_A,))
