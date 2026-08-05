"""Tests for the active MuSiQue experiment marker."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from graphragprov.experiments.activation import (
    ACTIVE_EXPERIMENT_FILENAME,
    MusiqueExperimentActivation,
    clear_musique_experiment_activation,
    load_musique_experiment_activation,
    write_musique_experiment_activation,
)
from graphragprov.experiments.manifest import MusiqueMaterializationManifest
from graphragprov.experiments.repository import InvalidExperimentIdError

_SOURCE_UNIT_ID = "u_c0a6b304b29f5aca50037fd196b85c825bacb4d708496bd0cda55d2b8ab70766"


def test_activation_round_trip(tmp_path: Path) -> None:
    manifest = _manifest()

    activation = MusiqueExperimentActivation.from_manifest(
        experiment_id="musique_4hop_5",
        manifest=manifest,
        activated_at=datetime(2026, 8, 5, 12, 0, tzinfo=UTC),
    )

    path = write_musique_experiment_activation(tmp_path, activation)

    assert path == tmp_path / ACTIVE_EXPERIMENT_FILENAME
    assert load_musique_experiment_activation(tmp_path) == activation


def test_missing_activation_returns_none(tmp_path: Path) -> None:
    assert load_musique_experiment_activation(tmp_path) is None


def test_activation_matches_exact_manifest() -> None:
    manifest = _manifest()

    activation = MusiqueExperimentActivation.from_manifest(
        experiment_id="musique_4hop_5", manifest=manifest
    )

    assert activation.matches(experiment_id="musique_4hop_5", manifest=manifest)

    assert not activation.matches(experiment_id="another_experiment", manifest=manifest)


def test_activation_rejects_replaced_manifest() -> None:
    original = _manifest(created_at=datetime(2026, 8, 5, 12, 0, tzinfo=UTC))
    replacement = _manifest(created_at=datetime(2026, 8, 5, 13, 0, tzinfo=UTC))

    activation = MusiqueExperimentActivation.from_manifest(
        experiment_id="musique_4hop_5", manifest=original
    )

    assert not activation.matches(experiment_id="musique_4hop_5", manifest=replacement)


def test_clear_activation_removes_marker(tmp_path: Path) -> None:
    activation = MusiqueExperimentActivation.from_manifest(
        experiment_id="musique_4hop_5", manifest=_manifest()
    )

    write_musique_experiment_activation(tmp_path, activation)

    assert clear_musique_experiment_activation(tmp_path)
    assert load_musique_experiment_activation(tmp_path) is None
    assert not clear_musique_experiment_activation(tmp_path)


def test_activation_rejects_unsafe_experiment_id() -> None:
    with pytest.raises(InvalidExperimentIdError, match="experiment ID must start"):
        MusiqueExperimentActivation.from_manifest(experiment_id="../outside", manifest=_manifest())


def test_activation_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / ACTIVE_EXPERIMENT_FILENAME
    path.write_text("{ invalid", encoding="utf-8")

    with pytest.raises(ValueError, match="active experiment contains invalid JSON"):
        load_musique_experiment_activation(tmp_path)


def test_activation_rejects_naive_datetime() -> None:
    manifest = _manifest()

    with pytest.raises(ValueError, match="activation time must be timezone-aware"):
        MusiqueExperimentActivation.from_manifest(
            experiment_id="musique_4hop_5",
            manifest=manifest,
            activated_at=datetime(2026, 8, 5, 12, 0),
        )


def _manifest(*, created_at: datetime | None = None) -> MusiqueMaterializationManifest:
    timestamp = created_at or datetime(2026, 8, 5, 11, 0, tzinfo=UTC)

    return MusiqueMaterializationManifest.from_dict(
        {
            "format": "musique-pilot-materialization-v2",
            "status": "complete",
            "created_at": timestamp.isoformat(),
            "dataset_path": "/datasets/musique.jsonl",
            "prompt_version": "grounded-rdf-v2",
            "model": "test-model",
            "max_tokens": 4096,
            "cache_root": ("runs/musique_4hop_5/extractions"),
            "graphdb": {
                "base_url": "http://localhost:7200",
                "repository": "graphragprov",
                "statements_before_run": 0,
            },
            "cases": [
                {
                    "case_id": "case-1",
                    "hop_count": 4,
                    "question": "What is the answer?",
                    "answer": "The answer",
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
                "graph_iris": [("urn:graphragprov:unit:u_c0a6b304b29f5aca")],
            },
        }
    )
