"""Read-only HTTP resources for materialized experiments."""

from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from graphragprov.api.dependencies import ExperimentRepositoryDependency
from graphragprov.benchmarks.musique.case import MusiqueCase
from graphragprov.benchmarks.musique.reader import load_case
from graphragprov.experiments import (
    ExperimentCaseNotFoundError,
    ExperimentNotFoundError,
    InvalidExperimentIdError,
    MusiqueMaterializationCase,
    StoredMusiqueExperiment,
)

router = APIRouter(prefix="/api/v1/experiments", tags=["experiments"])


class ExperimentResponse(BaseModel):
    """Public metadata describing one materialized experiment."""

    experiment_id: str
    benchmark: Literal["musique"] = "musique"
    status: Literal["complete", "partial"]
    created_at: datetime
    case_count: int
    hop_counts: tuple[int, ...]
    prompt_version: str
    extraction_model: str
    requested_source_count: int
    successful_extraction_count: int
    failed_extraction_count: int
    materialized_source_count: int
    statement_count: int


class ExperimentListResponse(BaseModel):
    """Collection of available materialized experiments."""

    items: tuple[ExperimentResponse, ...]
    total: int


class ExperimentCaseResponse(BaseModel):
    """Public benchmark-case metadata within one experiment."""

    experiment_id: str
    case_id: str
    question: str
    hop_count: int
    answerable: bool
    paragraph_count: int


class ExperimentCaseListResponse(BaseModel):
    """Collection of benchmark cases belonging to one experiment."""

    experiment_id: str
    items: tuple[ExperimentCaseResponse, ...]
    total: int


class BenchmarkParagraphResponse(BaseModel):
    """One benchmark paragraph shown as evaluation reference."""

    paragraph_index: int
    source_unit_id: str
    title: str
    text: str
    is_supporting: bool


class BenchmarkHopResponse(BaseModel):
    """One annotated reasoning hop from the benchmark."""

    hop_id: int
    question: str
    answer: str
    paragraph_support_index: int | None


class ExperimentCaseReferenceResponse(BaseModel):
    """Complete benchmark reference for one experiment case."""

    experiment_id: str
    case_id: str
    question: str
    gold_answer: str
    answer_aliases: tuple[str, ...]
    hop_count: int
    answerable: bool
    gold_support_indices: tuple[int, ...]
    decomposition: tuple[BenchmarkHopResponse, ...]
    paragraphs: tuple[BenchmarkParagraphResponse, ...]


@router.get("", response_model=ExperimentListResponse, summary="List materialized experiments")
def list_experiments(repository: ExperimentRepositoryDependency) -> ExperimentListResponse:
    """Return all validated experiments available to the API."""

    experiments = repository.list_experiments()
    items = tuple(_to_experiment_response(experiment) for experiment in experiments)

    return ExperimentListResponse(items=items, total=len(items))


@router.get(
    "/{experiment_id}", response_model=ExperimentResponse, summary="Get a materialized experiment"
)
def get_experiment(
    experiment_id: str, repository: ExperimentRepositoryDependency
) -> ExperimentResponse:
    """Return public metadata for one validated experiment."""

    experiment = _load_experiment(experiment_id, repository)

    return _to_experiment_response(experiment)


@router.get(
    "/{experiment_id}/cases",
    response_model=ExperimentCaseListResponse,
    summary="List cases in an experiment",
)
def list_experiment_cases(
    experiment_id: str, repository: ExperimentRepositoryDependency
) -> ExperimentCaseListResponse:
    """Return public case metadata for one experiment."""

    experiment = _load_experiment(experiment_id, repository)

    items = tuple(
        _to_case_response(experiment_id=experiment.experiment_id, case=case)
        for case in experiment.list_cases()
    )

    return ExperimentCaseListResponse(
        experiment_id=experiment.experiment_id, items=items, total=len(items)
    )


@router.get(
    "/{experiment_id}/cases/{case_id}",
    response_model=ExperimentCaseResponse,
    summary="Get a case from an experiment",
)
def get_experiment_case(
    experiment_id: str, case_id: str, repository: ExperimentRepositoryDependency
) -> ExperimentCaseResponse:
    """Return one public case resource from an experiment."""

    experiment = _load_experiment(experiment_id, repository)
    case = _load_experiment_case(experiment, case_id)

    return _to_case_response(experiment_id=experiment.experiment_id, case=case)


@router.get(
    "/{experiment_id}/cases/{case_id}/reference",
    response_model=ExperimentCaseReferenceResponse,
    summary="Get the benchmark reference for a case",
)
def get_experiment_case_reference(
    experiment_id: str, case_id: str, repository: ExperimentRepositoryDependency
) -> ExperimentCaseReferenceResponse:
    """Return the immutable benchmark reference for one case."""

    experiment = _load_experiment(experiment_id, repository)
    materialized_case = _load_experiment_case(experiment, case_id)

    try:
        benchmark_case = load_case(Path(experiment.manifest.dataset_path), case_id)
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

    return _to_case_reference_response(experiment_id=experiment.experiment_id, case=benchmark_case)


def _load_experiment(
    experiment_id: str, repository: ExperimentRepositoryDependency
) -> StoredMusiqueExperiment:
    """Load one experiment and translate domain errors to HTTP errors."""

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


def _load_experiment_case(
    experiment: StoredMusiqueExperiment, case_id: str
) -> MusiqueMaterializationCase:
    """Load one case recorded by an experiment."""

    try:
        return experiment.get_case(case_id)
    except ExperimentCaseNotFoundError as error:
        raise HTTPException(
            status_code=404, detail={"code": "experiment_case_not_found", "message": str(error)}
        ) from error


def _validate_benchmark_case(
    benchmark_case: MusiqueCase, materialized_case: MusiqueMaterializationCase
) -> None:
    """Ensure the external benchmark still matches the experiment snapshot."""

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


def _to_experiment_response(experiment: StoredMusiqueExperiment) -> ExperimentResponse:
    """Project an internal experiment into its safe HTTP representation."""

    manifest = experiment.manifest

    return ExperimentResponse(
        experiment_id=experiment.experiment_id,
        status=manifest.status,
        created_at=manifest.created_at,
        case_count=len(manifest.cases),
        hop_counts=tuple(sorted({case.hop_count for case in manifest.cases})),
        prompt_version=manifest.prompt_version,
        extraction_model=manifest.model,
        requested_source_count=manifest.requested_source_count,
        successful_extraction_count=(manifest.successful_extraction_count),
        failed_extraction_count=(manifest.failed_extraction_count),
        materialized_source_count=(manifest.materialization.source_count),
        statement_count=(manifest.materialization.statement_count),
    )


def _to_case_response(
    *, experiment_id: str, case: MusiqueMaterializationCase
) -> ExperimentCaseResponse:
    """Project a case snapshot into its safe HTTP representation."""

    return ExperimentCaseResponse(
        experiment_id=experiment_id,
        case_id=case.case_id,
        question=case.question,
        hop_count=case.hop_count,
        answerable=case.answerable,
        paragraph_count=len(case.paragraph_indices),
    )


def _to_case_reference_response(
    *, experiment_id: str, case: MusiqueCase
) -> ExperimentCaseReferenceResponse:
    """Project a benchmark case into its reference representation."""

    return ExperimentCaseReferenceResponse(
        experiment_id=experiment_id,
        case_id=case.case_id,
        question=case.question,
        gold_answer=case.answer,
        answer_aliases=case.answer_aliases,
        hop_count=case.hop_count,
        answerable=case.answerable,
        gold_support_indices=case.gold_support_indices,
        decomposition=tuple(
            BenchmarkHopResponse(
                hop_id=hop.hop_id,
                question=hop.question,
                answer=hop.answer,
                paragraph_support_index=(hop.paragraph_support_index),
            )
            for hop in case.decomposition
        ),
        paragraphs=tuple(
            BenchmarkParagraphResponse(
                paragraph_index=paragraph.index,
                source_unit_id=paragraph.unit_id,
                title=paragraph.title,
                text=paragraph.text,
                is_supporting=case.is_supporting(paragraph.index),
            )
            for paragraph in case.paragraphs
        ),
    )
