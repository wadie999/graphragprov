"""Opt-in integration test against a real GraphDB repository."""

import json
import os
from pathlib import Path

import pytest

from graphragprov.domain.source_unit import SourceUnit
from graphragprov.extraction.result import ExtractionResult
from graphragprov.graphdb.client import GRAPHDB_REPOSITORY_ENV, GRAPHDB_URL_ENV, GraphDBClient
from graphragprov.rdf.provenance import compact_unit_id, occurrence_token
from graphragprov.rdf.terms import rdf_triple, unit_graph_iri

GRAPHDB_INTEGRATION_RUN_ENV = "GRAPHRAGPROV_GRAPHDB_INTEGRATION_RUN"

OCCURRENCE_PREDICATE = "http://example.org/occurrenceOf"
SEMANTIC_PREDICATE_NAMESPACE = "urn:graphragprov:predicate:"


def test_real_extraction_round_trip_is_idempotent() -> None:
    run_directory = _integration_run_directory()

    source = _read_source(run_directory)
    extraction = ExtractionResult.from_json(
        (run_directory / "extraction.json").read_text(encoding="utf-8")
    )
    extraction.validate_against(source)

    rdf_content = (run_directory / "extraction-minimal.trig").read_text(encoding="utf-8")

    client = GraphDBClient.from_environment()
    graph = unit_graph_iri(source.unit_id).n3()

    expected_triples = {_triple_key(statement) for statement in extraction.statements}
    expected_tokens = {
        occurrence_token(unit_id=source.unit_id, statement=statement)
        for statement in extraction.statements
    }

    client.upload_trig_star(rdf_content)

    first_triple_count, first_tokens = _repository_snapshot(client=client, graph=graph)

    client.upload_trig_star(rdf_content)

    second_triple_count, second_tokens = _repository_snapshot(client=client, graph=graph)

    assert first_triple_count == len(expected_triples)
    assert first_tokens == expected_tokens

    assert second_triple_count == first_triple_count
    assert second_tokens == first_tokens

    sample_token = next(iter(first_tokens))

    assert sample_token.startswith(f"{compact_unit_id(source.unit_id)}:s=")
    assert ":p=" in sample_token
    assert ":o=" in sample_token
    assert ":t=" in sample_token


def _integration_run_directory() -> Path:
    required_variables = (GRAPHDB_URL_ENV, GRAPHDB_REPOSITORY_ENV, GRAPHDB_INTEGRATION_RUN_ENV)

    missing = [variable for variable in required_variables if not os.getenv(variable)]

    if missing:
        pytest.skip("GraphDB integration test requires: " + ", ".join(missing))

    run_directory = Path(os.environ[GRAPHDB_INTEGRATION_RUN_ENV])

    if not run_directory.is_dir():
        pytest.fail(f"integration run directory does not exist: {run_directory}")

    required_files = ("source.json", "extraction.json", "extraction-minimal.trig")

    for filename in required_files:
        path = run_directory / filename

        if not path.is_file():
            pytest.fail(f"integration artifact does not exist: {path}")

    return run_directory


def _read_source(run_directory: Path) -> SourceUnit:
    payload = json.loads((run_directory / "source.json").read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise TypeError("source.json must contain an object")

    unit_id = payload.get("unit_id")
    title = payload.get("title")
    text = payload.get("text")

    if not isinstance(unit_id, str):
        raise TypeError("source unit_id must be a string")

    if not isinstance(title, str):
        raise TypeError("source title must be a string")

    if not isinstance(text, str):
        raise TypeError("source text must be a string")

    return SourceUnit(unit_id=unit_id, title=title, text=text)


def _triple_key(statement: object) -> tuple[str, str, str]:
    subject, predicate, object_ = rdf_triple(statement)  # type: ignore[arg-type]

    return (subject.n3(), predicate.n3(), object_.n3())


def _repository_snapshot(*, client: GraphDBClient, graph: str) -> tuple[int, set[str]]:
    triple_result = client.query(
        f"""
        SELECT (COUNT(*) AS ?count)
        WHERE {{
          GRAPH {graph} {{
            ?s ?p ?o .
            FILTER(
              STRSTARTS(
                STR(?p),
                "{SEMANTIC_PREDICATE_NAMESPACE}"
              )
            )
          }}
        }}
        """
    )

    token_result = client.query(
        f"""
        SELECT ?token
        WHERE {{
          GRAPH {graph} {{
            << ?s ?p ?o >>
              <{OCCURRENCE_PREDICATE}>
              ?token .
          }}
        }}
        ORDER BY ?token
        """
    )

    return (_single_count(triple_result), _token_values(token_result))


def _single_count(result: dict[str, object]) -> int:
    results = result.get("results")
    assert isinstance(results, dict)

    bindings = results.get("bindings")
    assert isinstance(bindings, list)
    assert len(bindings) == 1

    row = bindings[0]
    assert isinstance(row, dict)

    count = row.get("count")
    assert isinstance(count, dict)

    value = count.get("value")
    assert isinstance(value, str)

    return int(value)


def _token_values(result: dict[str, object]) -> set[str]:
    results = result.get("results")
    assert isinstance(results, dict)

    bindings = results.get("bindings")
    assert isinstance(bindings, list)

    tokens: set[str] = set()

    for row in bindings:
        assert isinstance(row, dict)

        token = row.get("token")
        assert isinstance(token, dict)

        value = token.get("value")
        assert isinstance(value, str)

        tokens.add(value)

    return tokens
