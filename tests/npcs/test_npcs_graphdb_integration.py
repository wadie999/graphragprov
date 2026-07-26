"""Opt-in integration tests for NPCS rewriting followed by GraphDB execution."""

import os

import pytest

from graphragprov.domain import SourceUnit
from graphragprov.graphdb import GraphDBClient
from graphragprov.graphdb.client import GRAPHDB_REPOSITORY_ENV, GRAPHDB_URL_ENV
from graphragprov.hashing import source_unit_id
from graphragprov.npcs import NPCSClient
from graphragprov.npcs.client import NPCS_URL_ENV
from graphragprov.provenance import DecodedProvenance, SourceRegistry, decode_provenance_polynomial
from graphragprov.query import execute_provenance_query

GRAPH = "urn:graphragprov:unit:u_38162077dce1d7d1"

EXPECTED_ANSWER = "urn:graphragprov:entity:Florida%20Department%20of%20Corrections"

BROWARD_TITLE = "Broward Correctional Institution"

BROWARD_TEXT = (
    "The Broward Correctional Institution (BCI) was a correctional "
    "facility located in the former Country Estates CDP and in "
    "Southwest Ranches, Florida, operated by the Florida Department "
    "of Corrections. The Region IV Correctional Facility Office is "
    "located on the grounds of Broward Correctional Institution in "
    "the former Country Estates CDP. The prison was in proximity to "
    "Pembroke Pines. It was located along Sheridan Street, near "
    "U.S. Route 27."
)

BROWARD_SOURCE = SourceUnit(
    unit_id=source_unit_id(title=BROWARD_TITLE, text=BROWARD_TEXT),
    title=BROWARD_TITLE,
    text=BROWARD_TEXT,
)

SOURCE_REGISTRY = SourceRegistry((BROWARD_SOURCE,))

TOKEN_OPERATOR = "u_38162077dce1d7d1:s=tx:4-36:p=tx:148-159:o=tx:164-197:t=4b79dc23"

TOKEN_OFFICE = "u_38162077dce1d7d1:s=tx:203-241:p=tx:242-270:o=tx:271-303:t=5dae8a89"

TOKEN_SOUTHWEST = "u_38162077dce1d7d1:s=tx:4-36:p=tx:113-119:o=tx:120-146:t=2605283e"

TOKEN_COUNTRY_ESTATES = "u_38162077dce1d7d1:s=tx:4-36:p=tx:71-81:o=tx:86-112:t=4d7e942b"

EXPECTED_EVIDENCE_QUOTES: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    TOKEN_OPERATOR: (
        ("Broward Correctional Institution",),
        ("operated by",),
        ("Florida Department of Corrections",),
    ),
    TOKEN_OFFICE: (
        ("Region IV Correctional Facility Office",),
        ("is located on the grounds of",),
        ("Broward Correctional Institution",),
    ),
    TOKEN_SOUTHWEST: (
        ("Broward Correctional Institution",),
        ("and in",),
        ("Southwest Ranches, Florida",),
    ),
    TOKEN_COUNTRY_ESTATES: (
        ("Broward Correctional Institution",),
        ("located in",),
        ("former Country Estates CDP",),
    ),
}

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


def canonical_derivations(*derivations: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    """Return the same canonical ordering used by the polynomial parser."""

    return tuple(sorted(tuple(sorted(derivation)) for derivation in derivations))


@pytest.mark.parametrize(
    ("sparql", "expected_derivations"),
    [
        (QUERY_ONE_STATEMENT, canonical_derivations((TOKEN_OPERATOR,))),
        (QUERY_ONE_JOIN, canonical_derivations((TOKEN_OFFICE, TOKEN_OPERATOR))),
        (QUERY_TWO_JOINS, canonical_derivations((TOKEN_OFFICE, TOKEN_SOUTHWEST, TOKEN_OPERATOR))),
        (
            QUERY_ALTERNATIVE_DERIVATIONS,
            canonical_derivations(
                (TOKEN_OFFICE, TOKEN_SOUTHWEST, TOKEN_OPERATOR),
                (TOKEN_OFFICE, TOKEN_COUNTRY_ESTATES, TOKEN_OPERATOR),
            ),
        ),
    ],
)
def test_real_npcs_graphdb_query_path(
    sparql: str, expected_derivations: tuple[tuple[str, ...], ...]
) -> None:
    _require_services()

    execution = execute_provenance_query(
        sparql=sparql, graphdb=GraphDBClient.from_environment(), npcs=NPCSClient.from_environment()
    )

    assert _answers(execution.original_result) == {EXPECTED_ANSWER}
    assert _answers(execution.rewritten_result) == {EXPECTED_ANSWER}

    assert "http://example.org/occurrenceOf" in execution.rewritten_query
    assert "finalprovennacevariable" in execution.rewritten_query

    polynomial = _polynomial(execution.rewritten_result)

    decoded = decode_provenance_polynomial(polynomial, registry=SOURCE_REGISTRY)

    assert _decoded_token_derivations(decoded) == expected_derivations

    _assert_exact_source_evidence(decoded, expected_derivations=expected_derivations)


def _require_services() -> None:
    required = (GRAPHDB_URL_ENV, GRAPHDB_REPOSITORY_ENV, NPCS_URL_ENV)

    missing = [variable for variable in required if not os.getenv(variable)]

    if missing:
        pytest.skip("NPCS and GraphDB integration requires: " + ", ".join(missing))


def _answers(result: dict[str, object]) -> set[str]:
    bindings = _bindings(result)
    answers: set[str] = set()

    for binding in bindings:
        answer = binding.get("answer")
        assert isinstance(answer, dict)

        value = answer.get("value")
        assert isinstance(value, str)

        answers.add(value)

    return answers


def _polynomial(result: dict[str, object]) -> str:
    bindings = _bindings(result)
    assert len(bindings) == 1

    provenance = bindings[0].get("finalprovennacevariable")
    assert isinstance(provenance, dict)

    value = provenance.get("value")
    assert isinstance(value, str)
    assert value

    return value


def _decoded_token_derivations(decoded: DecodedProvenance) -> tuple[tuple[str, ...], ...]:
    return tuple(
        tuple(occurrence.token for occurrence in derivation.occurrences)
        for derivation in decoded.derivations
    )


def _assert_exact_source_evidence(
    decoded: DecodedProvenance, *, expected_derivations: tuple[tuple[str, ...], ...]
) -> None:
    expected_tokens = {token for derivation in expected_derivations for token in derivation}

    observed_tokens: set[str] = set()

    for derivation in decoded.derivations:
        for occurrence in derivation.occurrences:
            observed_tokens.add(occurrence.token)

            assert occurrence.source == BROWARD_SOURCE

            expected = EXPECTED_EVIDENCE_QUOTES[occurrence.token]

            subject_quotes = tuple(span.quote for span in occurrence.subject_evidence)
            predicate_quotes = tuple(span.quote for span in occurrence.predicate_evidence)
            object_quotes = tuple(span.quote for span in occurrence.object_evidence)

            assert subject_quotes == expected[0]
            assert predicate_quotes == expected[1]
            assert object_quotes == expected[2]

    assert observed_tokens == expected_tokens


def _bindings(result: dict[str, object]) -> list[dict[str, object]]:
    results = result.get("results")
    assert isinstance(results, dict)

    bindings = results.get("bindings")
    assert isinstance(bindings, list)

    typed_bindings: list[dict[str, object]] = []

    for binding in bindings:
        assert isinstance(binding, dict)
        typed_bindings.append(binding)

    return typed_bindings
