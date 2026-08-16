import pytest

from graphragprov.experiments.multihop_fidelity.config import (
    ArtifactOrigin,
    ExperimentConfig,
    QueryScope,
)


def test_artifact_origin_values_are_stable() -> None:
    assert ArtifactOrigin.REFERENCE.value == "reference"
    assert ArtifactOrigin.LEARNED.value == "learned"


def test_query_scope_values_are_stable() -> None:
    assert QueryScope.SUPPORT.value == "support"
    assert QueryScope.REPOSITORY.value == "repository"


def test_experiment_config_defaults_to_support_scope() -> None:
    config = ExperimentConfig(
        graph_origin=ArtifactOrigin.REFERENCE, query_origin=ArtifactOrigin.LEARNED
    )

    assert config.graph_origin is ArtifactOrigin.REFERENCE
    assert config.query_origin is ArtifactOrigin.LEARNED
    assert config.query_scope is QueryScope.SUPPORT
    assert config.max_source_attempts == 3
    assert config.max_query_attempts == 5


def test_experiment_config_accepts_repository_scope() -> None:
    config = ExperimentConfig(
        graph_origin=ArtifactOrigin.LEARNED,
        query_origin=ArtifactOrigin.REFERENCE,
        query_scope=QueryScope.REPOSITORY,
        max_source_attempts=4,
        max_query_attempts=7,
    )

    assert config.query_scope is QueryScope.REPOSITORY
    assert config.max_source_attempts == 4
    assert config.max_query_attempts == 7


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_source_attempts", 0),
        ("max_source_attempts", -1),
        ("max_query_attempts", 0),
        ("max_query_attempts", -1),
    ],
)
def test_experiment_config_rejects_non_positive_attempt_limits(field: str, value: int) -> None:
    kwargs = {
        "graph_origin": ArtifactOrigin.REFERENCE,
        "query_origin": ArtifactOrigin.REFERENCE,
        field: value,
    }

    with pytest.raises(ValueError, match=f"{field} must be at least 1"):
        ExperimentConfig(**kwargs)  # type: ignore[arg-type]


def test_experiment_config_is_immutable() -> None:
    config = ExperimentConfig(
        graph_origin=ArtifactOrigin.REFERENCE, query_origin=ArtifactOrigin.REFERENCE
    )

    with pytest.raises(AttributeError):
        config.query_scope = QueryScope.REPOSITORY  # type: ignore[misc]
