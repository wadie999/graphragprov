"""Tests for read-only experiment API resources."""

from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from graphragprov.api import create_app
from graphragprov.experiments import (
    ExperimentNotFoundError,
    MusiqueMaterializationManifest,
    StoredMusiqueExperiment,
    validate_experiment_id,
)


@dataclass(frozen=True, slots=True)
class StubExperimentRepository:
    """In-memory repository used by HTTP contract tests."""

    experiments: tuple[StoredMusiqueExperiment, ...]

    def list_experiments(self) -> tuple[StoredMusiqueExperiment, ...]:
        return self.experiments

    def get_experiment(
        self,
        experiment_id: str,
    ) -> StoredMusiqueExperiment:
        validated_id = validate_experiment_id(experiment_id)

        for experiment in self.experiments:
            if experiment.experiment_id == validated_id:
                return experiment

        raise ExperimentNotFoundError(
            f"experiment does not exist: {validated_id}"
        )


def test_list_experiments_returns_public_metadata() -> None:
    repository = StubExperimentRepository(
        experiments=(_stored_experiment(),)
    )

    with TestClient(
        create_app(experiment_repository=repository)
    ) as client:
        response = client.get("/api/v1/experiments")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "experiment_id": "musique_pilot",
                "benchmark": "musique",
                "status": "complete",
                "created_at": "2026-07-18T16:07:40Z",
                "case_count": 2,
                "hop_counts": [2, 4],
                "prompt_version": "grounded-rdf-v2",
                "extraction_model": "test-model",
                "requested_source_count": 2,
                "successful_extraction_count": 2,
                "failed_extraction_count": 0,
                "materialized_source_count": 2,
                "statement_count": 17,
            }
        ],
        "total": 1,
    }


def test_get_experiment_returns_one_public_resource() -> None:
    repository = StubExperimentRepository(
        experiments=(_stored_experiment(),)
    )

    with TestClient(
        create_app(experiment_repository=repository)
    ) as client:
        response = client.get(
            "/api/v1/experiments/musique_pilot"
        )

    assert response.status_code == 200

    payload = response.json()

    assert payload["experiment_id"] == "musique_pilot"
    assert payload["case_count"] == 2
    assert payload["hop_counts"] == [2, 4]


def test_experiment_response_hides_internal_and_gold_fields() -> None:
    repository = StubExperimentRepository(
        experiments=(_stored_experiment(),)
    )

    with TestClient(
        create_app(experiment_repository=repository)
    ) as client:
        response = client.get(
            "/api/v1/experiments/musique_pilot"
        )

    payload = response.json()

    assert "dataset_path" not in payload
    assert "cache_root" not in payload
    assert "graphdb" not in payload
    assert "cases" not in payload
    assert "answer" not in payload
    assert "gold_support_indices" not in payload


def test_get_experiment_returns_not_found_error() -> None:
    repository = StubExperimentRepository(experiments=())

    with TestClient(
        create_app(experiment_repository=repository)
    ) as client:
        response = client.get(
            "/api/v1/experiments/missing"
        )

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": "experiment_not_found",
            "message": "experiment does not exist: missing",
        }
    }


def test_get_experiment_rejects_invalid_identifier() -> None:
    repository = StubExperimentRepository(experiments=())

    with TestClient(
        create_app(experiment_repository=repository)
    ) as client:
        response = client.get(
            "/api/v1/experiments/bad!"
        )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == (
        "invalid_experiment_id"
    )


def _stored_experiment() -> StoredMusiqueExperiment:
    first_source_id = "u_" + ("0" * 63) + "1"
    second_source_id = "u_" + ("0" * 63) + "2"

    manifest = MusiqueMaterializationManifest.from_dict(
        {
            "format": "musique-pilot-materialization-v2",
            "status": "complete",
            "created_at": datetime(
                2026,
                7,
                18,
                16,
                7,
                40,
                tzinfo=UTC,
            ).isoformat(),
            "dataset_path": "/private/datasets/musique.jsonl",
            "prompt_version": "grounded-rdf-v2",
            "model": "test-model",
            "max_tokens": 4096,
            "cache_root": "/private/runs/extractions",
            "graphdb": {
                "base_url": "http://localhost:7200",
                "repository": "private-repository",
                "statements_before_run": 0,
            },
            "cases": [
                {
                    "case_id": "case-2-hop",
                    "hop_count": 2,
                    "question": "First question?",
                    "answer": "Hidden first answer",
                    "answer_aliases": [],
                    "answerable": True,
                    "paragraph_indices": [0, 1],
                    "gold_support_indices": [0],
                },
                {
                    "case_id": "case-4-hop",
                    "hop_count": 4,
                    "question": "Second question?",
                    "answer": "Hidden second answer",
                    "answer_aliases": [],
                    "answerable": True,
                    "paragraph_indices": [0, 1],
                    "gold_support_indices": [1],
                },
            ],
            "paragraph_occurrence_count": 4,
            "requested_source_count": 2,
            "successful_extraction_count": 2,
            "failed_extraction_count": 0,
            "new_outcome_count": 2,
            "reused_outcome_count": 0,
            "source_unit_ids": [
                first_source_id,
                second_source_id,
            ],
            "failures": [],
            "materialization": {
                "source_count": 2,
                "statement_count": 17,
                "graph_iris": [
                    "urn:graphragprov:unit:u_0000000000000000",
                    "urn:graphragprov:unit:u_0000000000000001",
                ],
            },
        }
    )

    return StoredMusiqueExperiment(
        experiment_id="musique_pilot",
        manifest=manifest,
    )