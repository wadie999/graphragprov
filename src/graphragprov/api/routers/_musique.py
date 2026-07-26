"""Shared MuSiQue resource loading for API routers."""

from pathlib import Path

from fastapi import HTTPException

from graphragprov.benchmarks.musique import MusiqueCase
from graphragprov.benchmarks.musique.reader import load_case
from graphragprov.experiments import (
    ExperimentCaseNotFoundError,
    ExperimentNotFoundError,
    InvalidExperimentIdError,
    MusiqueExperimentRepository,
    MusiqueMaterializationCase,
    StoredMusiqueExperiment,
)


def load_experiment(
    experiment_id: str, repository: MusiqueExperimentRepository
) -> StoredMusiqueExperiment:
    """Load one experiment and translate persistence errors."""

    try:
        return repository.get_experiment(experiment_id)
    except InvalidExperimentIdError as error:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_experiment_id", "message": str(error)}
        ) from error
    except ExperimentNotFoundError as error:
        raise HTTPException(
            status_code=404, detail={"code": "experiment_not_found", "message": str(error)}
        ) from error


def load_experiment_case(
    experiment: StoredMusiqueExperiment, case_id: str
) -> MusiqueMaterializationCase:
    """Load one case recorded by an experiment."""

    try:
        return experiment.get_case(case_id)
    except ExperimentCaseNotFoundError as error:
        raise HTTPException(
            status_code=404, detail={"code": "experiment_case_not_found", "message": str(error)}
        ) from error


def load_benchmark_case(
    experiment: StoredMusiqueExperiment, materialized_case: MusiqueMaterializationCase
) -> MusiqueCase:
    """Load and verify the benchmark case."""

    try:
        benchmark_case = load_case(
            Path(experiment.manifest.dataset_path), materialized_case.case_id
        )

        _validate_benchmark_case(benchmark_case, materialized_case)
    except (FileNotFoundError, KeyError, OSError, ValueError) as error:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "experiment_reference_unavailable",
                "message": (
                    f"the benchmark reference recorded by the experiment cannot be loaded: {error}"
                ),
            },
        ) from error

    return benchmark_case


def _validate_benchmark_case(
    benchmark_case: MusiqueCase, materialized_case: MusiqueMaterializationCase
) -> None:
    if benchmark_case.question != materialized_case.question:
        raise ValueError("benchmark question differs from the manifest")

    if benchmark_case.hop_count != materialized_case.hop_count:
        raise ValueError("benchmark hop count differs from the manifest")

    if benchmark_case.answerable != materialized_case.answerable:
        raise ValueError("benchmark answerable flag differs from the manifest")

    paragraph_indices = tuple(paragraph.index for paragraph in benchmark_case.paragraphs)

    if paragraph_indices != materialized_case.paragraph_indices:
        raise ValueError("benchmark paragraph indices differ from the manifest")

    if benchmark_case.gold_support_indices != materialized_case.gold_support_indices:
        raise ValueError("benchmark support indices differ from the manifest")
