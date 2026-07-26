"""Tests for read-only experiment API resources."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from graphragprov.api import create_app
from graphragprov.experiments import (
    ExperimentNotFoundError,
    MusiqueMaterializationManifest,
    StoredMusiqueExperiment,
    validate_experiment_id,
)
from graphragprov.hashing import source_unit_id


@dataclass(frozen=True, slots=True)
class StubExperimentRepository:
    """In-memory repository used by HTTP contract tests."""

    experiments: tuple[StoredMusiqueExperiment, ...]

    def list_experiments(self) -> tuple[StoredMusiqueExperiment, ...]:
        return self.experiments

    def get_experiment(self, experiment_id: str) -> StoredMusiqueExperiment:
        validated_id = validate_experiment_id(experiment_id)

        for experiment in self.experiments:
            if experiment.experiment_id == validated_id:
                return experiment

        raise ExperimentNotFoundError(f"experiment does not exist: {validated_id}")


def test_list_experiments_returns_public_metadata() -> None:
    repository = StubExperimentRepository(experiments=(_stored_experiment(),))

    with TestClient(create_app(experiment_repository=repository)) as client:
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
    repository = StubExperimentRepository(experiments=(_stored_experiment(),))

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments/musique_pilot")

    assert response.status_code == 200

    payload = response.json()

    assert payload["experiment_id"] == "musique_pilot"
    assert payload["case_count"] == 2
    assert payload["hop_counts"] == [2, 4]


def test_experiment_response_hides_internal_and_gold_fields() -> None:
    repository = StubExperimentRepository(experiments=(_stored_experiment(),))

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments/musique_pilot")

    payload = response.json()

    assert "dataset_path" not in payload
    assert "cache_root" not in payload
    assert "graphdb" not in payload
    assert "cases" not in payload
    assert "answer" not in payload
    assert "gold_support_indices" not in payload


def test_get_experiment_returns_not_found_error() -> None:
    repository = StubExperimentRepository(experiments=())

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments/missing")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {"code": "experiment_not_found", "message": "experiment does not exist: missing"}
    }


def test_get_experiment_rejects_invalid_identifier() -> None:
    repository = StubExperimentRepository(experiments=())

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments/bad!")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == ("invalid_experiment_id")


def test_list_experiment_cases_returns_public_metadata() -> None:
    repository = StubExperimentRepository(experiments=(_stored_experiment(),))

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments/musique_pilot/cases")

    assert response.status_code == 200
    assert response.json() == {
        "experiment_id": "musique_pilot",
        "items": [
            {
                "experiment_id": "musique_pilot",
                "case_id": "case-2-hop",
                "question": "First question?",
                "hop_count": 2,
                "answerable": True,
                "paragraph_count": 2,
            },
            {
                "experiment_id": "musique_pilot",
                "case_id": "case-4-hop",
                "question": "Second question?",
                "hop_count": 4,
                "answerable": True,
                "paragraph_count": 2,
            },
        ],
        "total": 2,
    }


def test_get_experiment_case_returns_one_public_resource() -> None:
    repository = StubExperimentRepository(experiments=(_stored_experiment(),))

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments/musique_pilot/cases/case-4-hop")

    assert response.status_code == 200
    assert response.json() == {
        "experiment_id": "musique_pilot",
        "case_id": "case-4-hop",
        "question": "Second question?",
        "hop_count": 4,
        "answerable": True,
        "paragraph_count": 2,
    }


def test_experiment_case_response_hides_gold_metadata() -> None:
    repository = StubExperimentRepository(experiments=(_stored_experiment(),))

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments/musique_pilot/cases/case-2-hop")

    payload = response.json()

    assert "answer" not in payload
    assert "answer_aliases" not in payload
    assert "gold_support_indices" not in payload
    assert "paragraph_indices" not in payload


def test_get_experiment_case_returns_not_found_error() -> None:
    repository = StubExperimentRepository(experiments=(_stored_experiment(),))

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments/musique_pilot/cases/missing")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": "experiment_case_not_found",
            "message": ("case does not exist in experiment musique_pilot: missing"),
        }
    }


def test_list_experiment_cases_reports_missing_experiment() -> None:
    repository = StubExperimentRepository(experiments=())

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments/missing/cases")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == ("experiment_not_found")


def test_get_experiment_case_reference_returns_benchmark_data(tmp_path: Path) -> None:
    dataset_path = tmp_path / "musique.jsonl"
    _write_test_musique_dataset(dataset_path)

    repository = StubExperimentRepository(
        experiments=(_stored_experiment(dataset_path=str(dataset_path)),)
    )

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments/musique_pilot/cases/case-2-hop/reference")

    assert response.status_code == 200
    assert response.json() == {
        "experiment_id": "musique_pilot",
        "case_id": "case-2-hop",
        "question": "First question?",
        "gold_answer": "Hidden first answer",
        "answer_aliases": [],
        "hop_count": 2,
        "answerable": True,
        "gold_support_indices": [0],
        "decomposition": [
            {
                "hop_id": 0,
                "question": "Intermediate question?",
                "answer": "Intermediate answer",
                "paragraph_support_index": 0,
            },
            {
                "hop_id": 1,
                "question": "Final subquestion?",
                "answer": "Hidden first answer",
                "paragraph_support_index": None,
            },
        ],
        "paragraphs": [
            {
                "paragraph_index": 0,
                "source_unit_id": source_unit_id(
                    title="Supporting paragraph", text="The supporting paragraph text."
                ),
                "title": "Supporting paragraph",
                "text": "The supporting paragraph text.",
                "is_supporting": True,
            },
            {
                "paragraph_index": 1,
                "source_unit_id": source_unit_id(
                    title="Distractor paragraph", text="The distractor paragraph text."
                ),
                "title": "Distractor paragraph",
                "text": "The distractor paragraph text.",
                "is_supporting": False,
            },
        ],
    }


def test_get_experiment_case_reference_reports_missing_case() -> None:
    repository = StubExperimentRepository(experiments=(_stored_experiment(),))

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments/musique_pilot/cases/missing/reference")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == ("experiment_case_not_found")


def test_get_experiment_case_reference_reports_unavailable_dataset(tmp_path: Path) -> None:
    missing_dataset = tmp_path / "missing.jsonl"

    repository = StubExperimentRepository(
        experiments=(_stored_experiment(dataset_path=str(missing_dataset)),)
    )

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments/musique_pilot/cases/case-2-hop/reference")

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == ("experiment_reference_unavailable")


def _stored_experiment(
    *, dataset_path: str = "/private/datasets/musique.jsonl"
) -> StoredMusiqueExperiment:
    first_source_id = "u_" + ("0" * 63) + "1"
    second_source_id = "u_" + ("0" * 63) + "2"

    manifest = MusiqueMaterializationManifest.from_dict(
        {
            "format": "musique-pilot-materialization-v2",
            "status": "complete",
            "created_at": datetime(2026, 7, 18, 16, 7, 40, tzinfo=UTC).isoformat(),
            "dataset_path": dataset_path,
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
            "source_unit_ids": [first_source_id, second_source_id],
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

    return StoredMusiqueExperiment(experiment_id="musique_pilot", manifest=manifest)


def _write_test_musique_dataset(path: Path) -> None:
    row = {
        "id": "case-2-hop",
        "question": "First question?",
        "answer": "Hidden first answer",
        "answer_aliases": [],
        "answerable": True,
        "paragraphs": [
            {
                "idx": 0,
                "title": "Supporting paragraph",
                "paragraph_text": ("The supporting paragraph text."),
                "is_supporting": True,
            },
            {
                "idx": 1,
                "title": "Distractor paragraph",
                "paragraph_text": ("The distractor paragraph text."),
                "is_supporting": False,
            },
        ],
        "question_decomposition": [
            {
                "id": 0,
                "question": "Intermediate question?",
                "answer": "Intermediate answer",
                "paragraph_support_idx": 0,
            },
            {
                "id": 1,
                "question": "Final subquestion?",
                "answer": "Hidden first answer",
                "paragraph_support_idx": None,
            },
        ],
    }

    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
