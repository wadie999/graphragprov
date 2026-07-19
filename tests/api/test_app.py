"""Tests for the FastAPI application foundation."""

from fastapi.testclient import TestClient

from graphragprov.api import create_app


def test_health_endpoint() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
    }


def test_openapi_schema_contains_service_metadata() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200

    schema = response.json()

    assert schema["info"]["title"] == "GraphRAGProv API"
    assert isinstance(schema["info"]["version"], str)
    assert schema["info"]["version"]
    assert "/health" in schema["paths"]


def test_application_factory_returns_independent_apps() -> None:
    first = create_app()
    second = create_app()

    assert first is not second
    assert first.router is not second.router
