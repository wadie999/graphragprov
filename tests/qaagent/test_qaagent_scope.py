"""Tests for deterministic QA-agent graph scoping."""

import pytest

from graphragprov.qaagent import compile_scoped_select_query
from graphragprov.rdf.terms import unit_graph_iri

UNIT_A = "u_" + "a" * 64
UNIT_B = "u_" + "b" * 64

SEMANTIC_QUERY = """
PREFIX ex: <urn:example:>

SELECT DISTINCT ?answer
WHERE {
  ex:subject ex:predicate ?answer .
}
"""


def test_query_is_scoped_to_sorted_unique_graphs() -> None:
    scoped = compile_scoped_select_query(SEMANTIC_QUERY, source_unit_ids=(UNIT_B, UNIT_A, UNIT_B))

    graph_a = unit_graph_iri(UNIT_A)
    graph_b = unit_graph_iri(UNIT_B)

    assert scoped == (
        "PREFIX ex: <urn:example:>\n"
        "\n"
        "SELECT DISTINCT ?answer\n"
        f"FROM <{graph_a}>\n"
        f"FROM <{graph_b}>\n"
        "WHERE {\n"
        "  ex:subject ex:predicate ?answer .\n"
        "}"
    )


def test_repository_scope_adds_no_dataset_clause() -> None:
    scoped = compile_scoped_select_query(SEMANTIC_QUERY, source_unit_ids=None)

    assert scoped == SEMANTIC_QUERY.strip()
    assert "FROM <" not in scoped


def test_scoped_query_requires_source_units() -> None:
    with pytest.raises(ValueError, match="at least one source unit"):
        compile_scoped_select_query(SEMANTIC_QUERY, source_unit_ids=())


def test_empty_query_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        compile_scoped_select_query("   ", source_unit_ids=(UNIT_A,))


@pytest.mark.parametrize(
    "query",
    [
        "ASK WHERE { ?s ?p ?o }",
        "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }",
        "DESCRIBE ?s WHERE { ?s ?p ?o }",
    ],
)
def test_only_select_queries_are_accepted(query: str) -> None:
    with pytest.raises(ValueError, match="must be a SELECT query"):
        compile_scoped_select_query(query, source_unit_ids=(UNIT_A,))


@pytest.mark.parametrize(
    ("fragment", "expected"),
    [
        ("FROM <urn:unauthorized>", "FROM"),
        ("GRAPH <urn:unauthorized>", "GRAPH"),
        ("SERVICE <https://example.org/sparql>", "SERVICE"),
        ("INSERT DATA", "update operation"),
        ("MOVE GRAPH <urn:a> TO GRAPH <urn:b>", "GRAPH"),
    ],
)
def test_llm_cannot_control_graph_access(fragment: str, expected: str) -> None:
    query = f"SELECT ?answer\n{fragment}\nWHERE {{ ?s ?p ?answer }}"

    with pytest.raises(ValueError, match=expected):
        compile_scoped_select_query(query, source_unit_ids=(UNIT_A,))


def test_update_keyword_inside_iri_is_not_treated_as_update_operation() -> None:
    query = """
SELECT ?answer
WHERE {
  <urn:graphragprov:entity:Move%20%281970%20film%29>
    <urn:graphragprov:predicate:director>
    ?answer .
}
"""

    scoped = compile_scoped_select_query(query, source_unit_ids=(UNIT_A,))

    assert "<urn:graphragprov:entity:Move%20%281970%20film%29>" in scoped
    assert f"FROM <{unit_graph_iri(UNIT_A)}>" in scoped


def test_control_words_inside_terms_are_not_interpreted_as_syntax() -> None:
    query = """
SELECT ?graph ?answer
WHERE {
  <urn:example:GRAPH>
    <urn:example:FROM>
    ?graph .
  BIND("SERVICE MOVE INSERT DELETE" AS ?answer)
}
"""

    scoped = compile_scoped_select_query(query, source_unit_ids=(UNIT_A,))

    assert "?graph" in scoped
    assert "<urn:example:GRAPH>" in scoped
    assert '"SERVICE MOVE INSERT DELETE"' in scoped


def test_comment_keywords_are_not_interpreted_as_syntax() -> None:
    query = """
SELECT ?answer
# MOVE GRAPH SERVICE FROM INSERT DELETE
WHERE {
  ?s ?p ?answer .
}
"""

    scoped = compile_scoped_select_query(query, source_unit_ids=(UNIT_A,))

    assert "# MOVE GRAPH SERVICE FROM INSERT DELETE" in scoped


def test_explicit_where_clause_is_required() -> None:
    with pytest.raises(ValueError, match="explicit WHERE clause"):
        compile_scoped_select_query("SELECT ?answer { ?s ?p ?answer }", source_unit_ids=(UNIT_A,))
