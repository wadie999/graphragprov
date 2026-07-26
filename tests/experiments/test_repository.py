"""Tests for filesystem-backed experiment persistence."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from graphragprov.experiments import (
    ExperimentCaseNotFoundError,
    ExperimentNotFoundError,
    FilesystemMusiqueExperimentRepository,
    InvalidExperimentIdError,
    MusiqueMaterializationManifest,
    write_musique_materialization_manifest,
)

_SOURCE_UNIT_ID = "u_c0a6b304b29f5aca50037fd196b85c825bacb4d708496bd0cda55d2b8ab70766"


def test_repository_lists_valid_experiments_in_identifier_order(tmp_path: Path) -> None:
    _store_experiment(tmp_path, experiment_id="second", case_id="case-2")
    _store_experiment(tmp_path, experiment_id="first", case_id="case-1")

    unrelated_directory = tmp_path / "not-an-experiment"
    unrelated_directory.mkdir()
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")

    repository = FilesystemMusiqueExperimentRepository(tmp_path)

    experiments = repository.list_experiments()

    assert tuple(experiment.experiment_id for experiment in experiments) == ("first", "second")
    assert experiments[0].manifest.cases[0].case_id == "case-1"
    assert experiments[1].manifest.cases[0].case_id == "case-2"


def test_repository_returns_one_experiment(tmp_path: Path) -> None:
    _store_experiment(tmp_path, experiment_id="musique_pilot", case_id="case-1")

    repository = FilesystemMusiqueExperimentRepository(tmp_path)

    experiment = repository.get_experiment("musique_pilot")

    assert experiment.experiment_id == "musique_pilot"
    assert experiment.manifest.cases[0].case_id == "case-1"


def test_repository_returns_empty_collection_when_root_does_not_exist(tmp_path: Path) -> None:
    repository = FilesystemMusiqueExperimentRepository(tmp_path / "missing")

    assert repository.list_experiments() == ()


def test_repository_rejects_unsafe_experiment_identifier(tmp_path: Path) -> None:
    repository = FilesystemMusiqueExperimentRepository(tmp_path)

    with pytest.raises(InvalidExperimentIdError, match="experiment ID must start"):
        repository.get_experiment("../outside")


def test_repository_reports_missing_experiment(tmp_path: Path) -> None:
    repository = FilesystemMusiqueExperimentRepository(tmp_path)

    with pytest.raises(ExperimentNotFoundError, match="experiment does not exist: missing"):
        repository.get_experiment("missing")


def _store_experiment(root: Path, *, experiment_id: str, case_id: str) -> None:
    manifest = MusiqueMaterializationManifest.from_dict(
        {
            "format": "musique-pilot-materialization-v2",
            "status": "complete",
            "created_at": datetime(2026, 7, 18, 16, 7, 40, tzinfo=UTC).isoformat(),
            "dataset_path": "/datasets/musique.jsonl",
            "prompt_version": "grounded-rdf-v2",
            "model": "test-model",
            "max_tokens": 4096,
            "cache_root": f"runs/{experiment_id}/extractions",
            "graphdb": {
                "base_url": "http://localhost:7200",
                "repository": "test-repository",
                "statements_before_run": 0,
            },
            "cases": [
                {
                    "case_id": case_id,
                    "hop_count": 1,
                    "question": "Where was the person born?",
                    "answer": "Toulouse",
                    "answer_aliases": [],
                    "answerable": True,
                    "paragraph_indices": [0],
                    "gold_support_indices": [0],
                }
            ],
            "paragraph_occurrence_count": 1,
            "requested_source_count": 1,
            "successful_extraction_count": 1,
            "failed_extraction_count": 0,
            "new_outcome_count": 1,
            "reused_outcome_count": 0,
            "source_unit_ids": [_SOURCE_UNIT_ID],
            "failures": [],
            "materialization": {
                "source_count": 1,
                "statement_count": 1,
                "graph_iris": ["urn:graphragprov:unit:u_c0a6b304b29f5aca"],
            },
        }
    )

    write_musique_materialization_manifest(root / experiment_id / "materialization.json", manifest)


def test_stored_experiment_returns_one_case(tmp_path: Path) -> None:
    _store_experiment(tmp_path, experiment_id="musique_pilot", case_id="case-1")

    repository = FilesystemMusiqueExperimentRepository(tmp_path)
    experiment = repository.get_experiment("musique_pilot")

    case = experiment.get_case("case-1")

    assert case.case_id == "case-1"
    assert case.question == "Where was the person born?"


def test_stored_experiment_reports_missing_case(tmp_path: Path) -> None:
    _store_experiment(tmp_path, experiment_id="musique_pilot", case_id="case-1")

    repository = FilesystemMusiqueExperimentRepository(tmp_path)
    experiment = repository.get_experiment("musique_pilot")

    with pytest.raises(
        ExperimentCaseNotFoundError,
        match=("case does not exist in experiment musique_pilot: missing"),
    ):
        experiment.get_case("missing")
