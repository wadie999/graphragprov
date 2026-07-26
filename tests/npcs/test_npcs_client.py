"""Tests for the minimal NPCS HTTP client."""

import json
from urllib.error import URLError
from urllib.request import Request

import pytest

import graphragprov.npcs.client as client_module
from graphragprov.npcs.client import NPCS_URL_ENV, NPCSClient, NPCSError


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exception_type: object, exception: object, traceback: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_client_is_created_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(NPCS_URL_ENV, "http://localhost:8082/")

    client = NPCSClient.from_environment()

    assert client.base_url == "http://localhost:8082/"
    assert client.rewrite_endpoint == ("http://localhost:8082/api/content/rewrite")


def test_rewrite_sends_expected_request(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_requests: list[tuple[Request, float]] = []

    rewritten_query = "SELECT ?answer ?finalprovennacevariable WHERE { ?s ?p ?answer }"

    def fake_urlopen(request: Request, *, timeout: float) -> _FakeResponse:
        captured_requests.append((request, timeout))
        return _FakeResponse(rewritten_query.encode())

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    client = NPCSClient(base_url="http://localhost:8082", timeout_seconds=12.0)

    original_query = "SELECT ?answer WHERE { ?s ?p ?answer }"

    result = client.rewrite(original_query)

    assert result == rewritten_query
    assert len(captured_requests) == 1

    request, timeout = captured_requests[0]

    assert request.full_url == ("http://localhost:8082/api/content/rewrite")
    assert request.get_method() == "POST"
    assert request.get_header("Content-type") == "application/json"
    assert timeout == 12.0
    assert isinstance(request.data, bytes)

    payload = json.loads(request.data.decode())

    assert payload == {"input1": "SPARQL_Star", "input2": "query", "input3": original_query}


def test_empty_rewritten_query_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: Request, *, timeout: float) -> _FakeResponse:
        del request
        del timeout
        return _FakeResponse(b"   \n")

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    client = NPCSClient(base_url="http://localhost:8082")

    with pytest.raises(NPCSError, match="NPCS returned an empty rewritten query"):
        client.rewrite("SELECT ?s WHERE { ?s ?p ?o }")


def test_connection_failure_becomes_npcs_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_urlopen(request: Request, *, timeout: float) -> _FakeResponse:
        del request
        del timeout
        raise URLError("connection refused")

    monkeypatch.setattr(client_module, "urlopen", failing_urlopen)

    client = NPCSClient(base_url="http://localhost:8082")

    with pytest.raises(NPCSError, match="could not reach NPCS: connection refused"):
        client.rewrite("SELECT ?s WHERE { ?s ?p ?o }")
