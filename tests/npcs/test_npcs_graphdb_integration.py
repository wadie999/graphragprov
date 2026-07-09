"""Opt-in integration tests for NPCS rewriting followed by GraphDB execution."""

import os

import pytest

from graphragprov.graphdb import GraphDBClient
from graphragprov.graphdb.client import (
    GRAPHDB_REPOSITORY_ENV,
    GRAPHDB_URL_ENV,
)
from graphragprov.npcs import NPCSClient
from graphragprov.npcs.client import NPCS_URL_ENV
from graphragprov.query import execute_provenance_query

GRAPH = "urn:graphragprov:unit:u_38162077dce1d7d1"

EXPECTED_ANSWER = "urn:graphragprov:entity:Florida%20Department%20of%20Corrections"

TOKEN_OPERATOR = "u_38162077dce1d7d1:s=tx:4-36:p=tx:148-159:o=tx:164-197:t=4b79dc23"
TOKEN_OFFICE = "u_38162077dce1d7d1:s=tx:203-241:p=tx:242-270:o=tx:271-303:t=5dae8a89"
TOKEN_SOUTHWEST = "u_38162077dce1d7d1:s=tx:4-36:p=tx:113-119:o=tx:120-146:t=2605283e"
TOKEN_COUNTRY_ESTATES = "u_38162077dce1d7d1:s=tx:4-36:p=tx:71-81:o=tx:86-112:t=4d7e942b"

QUERY_ONE_STATEMENT = f"""
SELECT ?answer
FROM <{GRAPH}>
WHERE {{
  <urn:graphragprov:entity:Broward%20Correctional%20Institution>
    <urn:graphragprov:predicate:operatedBy>
    ?answer .
}}
"""

QUERY_ONE_JOIN = f"""
SELECT ?answer
FROM <{GRAPH}>
WHERE {{
  <urn:graphragprov:entity:Region%20IV%20Correctional%20Facility%20Office>
    <urn:graphragprov:predicate:locatedIn>
    ?institution .

  ?institution
    <urn:graphragprov:predicate:operatedBy>
    ?answer .
}}
"""

QUERY_TWO_JOINS = f"""
SELECT ?answer
FROM <{GRAPH}>
WHERE {{
  <urn:graphragprov:entity:Region%20IV%20Correctional%20Facility%20Office>
    <urn:graphragprov:predicate:locatedIn>
    ?institution .

  ?institution
    <urn:graphragprov:predicate:locatedIn>
    <urn:graphragprov:entity:Southwest%20Ranches%2C%20Florida> .

  ?institution
    <urn:graphragprov:predicate:operatedBy>
    ?answer .
}}
"""

QUERY_ALTERNATIVE_DERIVATIONS = f"""
SELECT ?answer
FROM <{GRAPH}>
WHERE {{
  <urn:graphragprov:entity:Region%20IV%20Correctional%20Facility%20Office>
    <urn:graphragprov:predicate:locatedIn>
    ?institution .

  ?institution
    <urn:graphragprov:predicate:locatedIn>
    ?place .

  ?institution
    <urn:graphragprov:predicate:operatedBy>
    ?answer .
}}
"""


@pytest.mark.parametrize(
    (
        "sparql",
        "expected_tokens",
        "expected_product_count",
    ),
    [
        (
            QUERY_ONE_STATEMENT,
            {TOKEN_OPERATOR},
            1,
        ),
        (
            QUERY_ONE_JOIN,
            {TOKEN_OFFICE, TOKEN_OPERATOR},
            1,
        ),
        (
            QUERY_TWO_JOINS,
            {
                TOKEN_OFFICE,
                TOKEN_SOUTHWEST,
                TOKEN_OPERATOR,
            },
            1,
        ),
        (
            QUERY_ALTERNATIVE_DERIVATIONS,
            {
                TOKEN_OFFICE,
                TOKEN_SOUTHWEST,
                TOKEN_COUNTRY_ESTATES,
                TOKEN_OPERATOR,
            },
            2,
        ),
    ],
)
def test_real_npcs_graphdb_query_path(
    sparql: str,
    expected_tokens: set[str],
    expected_product_count: int,
) -> None:
    _require_services()

    execution = execute_provenance_query(
        sparql=sparql,
        graphdb=GraphDBClient.from_environment(),
        npcs=NPCSClient.from_environment(),
    )

    assert _answers(execution.original_result) == {EXPECTED_ANSWER}
    assert _answers(execution.rewritten_result) == {EXPECTED_ANSWER}

    assert "http://example.org/occurrenceOf" in (execution.rewritten_query)
    assert "finalprovennacevariable" in execution.rewritten_query

    polynomial = _polynomial(execution.rewritten_result)

    for token in expected_tokens:
        assert token in polynomial

    assert polynomial.startswith("⊕(")
    assert polynomial.count("⊗") == expected_product_count


def _require_services() -> None:
    required = (
        GRAPHDB_URL_ENV,
        GRAPHDB_REPOSITORY_ENV,
        NPCS_URL_ENV,
    )

    missing = [variable for variable in required if not os.getenv(variable)]

    if missing:
        pytest.skip("NPCS and GraphDB integration requires: " + ", ".join(missing))


def _answers(
    result: dict[str, object],
) -> set[str]:
    bindings = _bindings(result)
    answers: set[str] = set()

    for binding in bindings:
        answer = binding.get("answer")
        assert isinstance(answer, dict)

        value = answer.get("value")
        assert isinstance(value, str)

        answers.add(value)

    return answers


def _polynomial(
    result: dict[str, object],
) -> str:
    bindings = _bindings(result)
    assert len(bindings) == 1

    provenance = bindings[0].get("finalprovennacevariable")
    assert isinstance(provenance, dict)

    value = provenance.get("value")
    assert isinstance(value, str)
    assert value

    return value


def _bindings(
    result: dict[str, object],
) -> list[dict[str, object]]:
    results = result.get("results")
    assert isinstance(results, dict)

    bindings = results.get("bindings")
    assert isinstance(bindings, list)

    typed_bindings: list[dict[str, object]] = []

    for binding in bindings:
        assert isinstance(binding, dict)
        typed_bindings.append(binding)

    return typed_bindings
