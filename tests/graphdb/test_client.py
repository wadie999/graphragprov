"""Tests for the minimal GraphDB HTTP client."""

import json
from urllib.error import URLError
from urllib.parse import parse_qs
from urllib.request import Request

import pytest

import graphragprov.graphdb.client as client_module
from graphragprov.graphdb.client import (
    GRAPHDB_PASSWORD_ENV,
    GRAPHDB_REPOSITORY_ENV,
    GRAPHDB_URL_ENV,
    GRAPHDB_USERNAME_ENV,
    SPARQL_RESULTS_MEDIA_TYPE,
    TRIG_STAR_MEDIA_TYPE,
    GraphDBClient,
    GraphDBError,
)


class _FakeResponse:
    def __init__(self, *, status: int, body: bytes = b"") -> None:
        self._status = status
        self._body = body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exception_type: object, exception: object, traceback: object) -> None:
        return None

    def getcode(self) -> int:
        return self._status

    def read(self) -> bytes:
        return self._body


def test_client_is_created_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(GRAPHDB_URL_ENV, "http://localhost:7200/")
    monkeypatch.setenv(GRAPHDB_REPOSITORY_ENV, "graph repo")
    monkeypatch.setenv(GRAPHDB_USERNAME_ENV, "wadie")
    monkeypatch.setenv(GRAPHDB_PASSWORD_ENV, "secret")

    client = GraphDBClient.from_environment()

    assert client.base_url == "http://localhost:7200/"
    assert client.repository == "graph repo"
    assert client.username == "wadie"
    assert client.password == "secret"
    assert client.repository_endpoint == ("http://localhost:7200/repositories/graph%20repo")


def test_upload_trig_star_sends_expected_request(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_requests: list[tuple[Request, float]] = []

    def fake_urlopen(request: Request, *, timeout: float) -> _FakeResponse:
        captured_requests.append((request, timeout))
        return _FakeResponse(status=204)

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    client = GraphDBClient(
        base_url="http://localhost:7200", repository="graphragprov", timeout_seconds=12.0
    )

    content = (
        "@prefix textprov: <http://example.org/> .\n"
        "GRAPH <urn:test> { <urn:s> <urn:p> <urn:o> . }\n"
    )

    client.upload_trig_star(content)

    assert len(captured_requests) == 1

    request, timeout = captured_requests[0]

    assert request.full_url == ("http://localhost:7200/repositories/graphragprov/statements")
    assert request.get_method() == "POST"
    assert request.data == content.encode()
    assert request.get_header("Content-type") == TRIG_STAR_MEDIA_TYPE
    assert timeout == 12.0


def test_query_sends_sparql_and_decodes_json(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_requests: list[Request] = []

    response_payload = {
        "head": {"vars": ["count"]},
        "results": {"bindings": [{"count": {"type": "literal", "value": "8"}}]},
    }

    def fake_urlopen(request: Request, *, timeout: float) -> _FakeResponse:
        del timeout
        captured_requests.append(request)

        return _FakeResponse(status=200, body=json.dumps(response_payload).encode())

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    client = GraphDBClient(base_url="http://localhost:7200", repository="graphragprov")

    sparql = "SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }"

    result = client.query(sparql)

    assert result == response_payload
    assert len(captured_requests) == 1

    request = captured_requests[0]

    assert request.full_url == ("http://localhost:7200/repositories/graphragprov")
    assert request.get_method() == "POST"
    assert request.get_header("Accept") == SPARQL_RESULTS_MEDIA_TYPE
    assert isinstance(request.data, bytes)

    form = parse_qs(request.data.decode())

    assert form == {"query": [sparql]}


def test_connection_failure_becomes_graphdb_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_urlopen(request: Request, *, timeout: float) -> _FakeResponse:
        del request
        del timeout
        raise URLError("connection refused")

    monkeypatch.setattr(client_module, "urlopen", failing_urlopen)

    client = GraphDBClient(base_url="http://localhost:7200", repository="graphragprov")

    with pytest.raises(GraphDBError, match="could not reach GraphDB: connection refused"):
        client.query("ASK { ?s ?p ?o }")
