"""Tests for configurable MuSiQue materialization experiments."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import graphragprov.experiments.musique_materialization as materialization_module
from graphragprov.experiments.musique_materialization import (
    MusiqueExperimentConfiguration,
    run_musique_experiment,
)


class _UnexpectedGraphDB:
    repository = "test-repository"

    def query(self, sparql: str) -> dict[str, object]:
        del sparql
        raise AssertionError("GraphDB must not be queried")


class _NonEmptyGraphDB:
    repository = "test-repository"

    def query(self, sparql: str) -> dict[str, object]:
        del sparql

        return {"results": {"bindings": [{"count": {"value": "12"}}]}}


def test_configuration_uses_standard_experiment_layout(tmp_path: Path) -> None:
    configuration = _configuration(tmp_path)

    assert configuration.run_root == (tmp_path / "runs" / "musique_4hop_5")
    assert configuration.manifest_path == (
        tmp_path / "runs" / "musique_4hop_5" / "materialization.json"
    )
    assert configuration.source_catalog_path == (
        tmp_path / "runs" / "musique_4hop_5" / "source-units.json"
    )
    assert configuration.resolved_cache_root == (
        tmp_path / "runs" / "musique_4hop_5" / "extractions" / "grounded-rdf-v2" / "test-model"
    )


def test_experiment_requires_exact_requested_case_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configuration = _configuration(tmp_path, limit=5)

    monkeypatch.setattr(materialization_module, "select_cases", lambda *args, **kwargs: ())

    with pytest.raises(ValueError, match=("requested 5 matching 4-hop MuSiQue cases, but found 0")):
        run_musique_experiment(
            configuration,
            generate_response=_unexpected_generator,
            graphdb=_UnexpectedGraphDB(),  # type: ignore[arg-type]
        )


def test_non_empty_repository_requires_explicit_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configuration = _configuration(tmp_path, limit=1, replace_repository=False)

    case = SimpleNamespace(case_id="case-1", hop_count=4, answerable=True, paragraphs=())

    monkeypatch.setattr(materialization_module, "select_cases", lambda *args, **kwargs: (case,))
    monkeypatch.setattr(materialization_module, "collect_musique_source_units", lambda cases: ())

    with pytest.raises(
        ValueError,
        match=(
            "GraphDB repository is not empty "
            r"\(12 statements\)"
        ),
    ):
        run_musique_experiment(
            configuration,
            generate_response=_unexpected_generator,
            graphdb=_NonEmptyGraphDB(),  # type: ignore[arg-type]
        )


def _configuration(tmp_path: Path, **overrides: Any) -> MusiqueExperimentConfiguration:
    values: dict[str, Any] = {
        "experiment_id": "musique_4hop_5",
        "dataset_path": tmp_path / "musique.jsonl",
        "runs_root": tmp_path / "runs",
        "hop_count": 4,
        "limit": 5,
        "answerable_only": True,
        "model": "test-model",
        "max_tokens": 4096,
        "cache_root": None,
        "retry_failures": False,
        "replace_repository": False,
        "verbose": True,
    }
    values.update(overrides)

    return MusiqueExperimentConfiguration(**values)


def _unexpected_generator(prompt: str) -> str:
    del prompt
    raise AssertionError("the model must not be called")
