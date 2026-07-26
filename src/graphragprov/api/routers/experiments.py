"""Read-only HTTP resources for materialized experiments."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from graphragprov.api.dependencies import ExperimentRepositoryDependency
from graphragprov.api.routers._musique import (
    load_benchmark_case,
    load_experiment,
    load_experiment_case,
)
from graphragprov.benchmarks.musique import MusiqueCase
from graphragprov.experiments import MusiqueMaterializationCase, StoredMusiqueExperiment

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
    """Collection of available experiments."""

    items: tuple[ExperimentResponse, ...]
    total: int


class ExperimentCaseResponse(BaseModel):
    """Public metadata for one benchmark case."""

    experiment_id: str
    case_id: str
    question: str
    hop_count: int
    answerable: bool
    paragraph_count: int


class ExperimentCaseListResponse(BaseModel):
    """Cases belonging to one experiment."""

    experiment_id: str
    items: tuple[ExperimentCaseResponse, ...]
    total: int


class BenchmarkParagraphResponse(BaseModel):
    """One source paragraph from the benchmark."""

    paragraph_index: int
    source_unit_id: str
    title: str
    text: str
    is_supporting: bool


class BenchmarkHopResponse(BaseModel):
    """One benchmark decomposition hop."""

    hop_id: int
    question: str
    answer: str
    paragraph_support_index: int | None


class ExperimentCaseReferenceResponse(BaseModel):
    """Fixed benchmark reference for one case."""

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
    experiments = repository.list_experiments()

    items = tuple(_to_experiment_response(experiment) for experiment in experiments)

    return ExperimentListResponse(items=items, total=len(items))


@router.get(
    "/{experiment_id}", response_model=ExperimentResponse, summary="Get a materialized experiment"
)
def get_experiment(
    experiment_id: str, repository: ExperimentRepositoryDependency
) -> ExperimentResponse:
    return _to_experiment_response(load_experiment(experiment_id, repository))


@router.get(
    "/{experiment_id}/cases",
    response_model=ExperimentCaseListResponse,
    summary="List cases in an experiment",
)
def list_experiment_cases(
    experiment_id: str, repository: ExperimentRepositoryDependency
) -> ExperimentCaseListResponse:
    experiment = load_experiment(experiment_id, repository)

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
    experiment = load_experiment(experiment_id, repository)

    case = load_experiment_case(experiment, case_id)

    return _to_case_response(experiment_id=experiment.experiment_id, case=case)


@router.get(
    "/{experiment_id}/cases/{case_id}/reference",
    response_model=ExperimentCaseReferenceResponse,
    summary="Get the benchmark reference for a case",
)
def get_experiment_case_reference(
    experiment_id: str, case_id: str, repository: ExperimentRepositoryDependency
) -> ExperimentCaseReferenceResponse:
    experiment = load_experiment(experiment_id, repository)

    materialized_case = load_experiment_case(experiment, case_id)

    benchmark_case = load_benchmark_case(experiment, materialized_case)

    return _to_case_reference_response(experiment_id=experiment.experiment_id, case=benchmark_case)


def _to_experiment_response(experiment: StoredMusiqueExperiment) -> ExperimentResponse:
    manifest = experiment.manifest

    return ExperimentResponse(
        experiment_id=experiment.experiment_id,
        status=manifest.status,
        created_at=manifest.created_at,
        case_count=len(manifest.cases),
        hop_counts=tuple(sorted({case.hop_count for case in manifest.cases})),
        prompt_version=manifest.prompt_version,
        extraction_model=manifest.model,
        requested_source_count=(manifest.requested_source_count),
        successful_extraction_count=(manifest.successful_extraction_count),
        failed_extraction_count=(manifest.failed_extraction_count),
        materialized_source_count=(manifest.materialization.source_count),
        statement_count=(manifest.materialization.statement_count),
    )


def _to_case_response(
    *, experiment_id: str, case: MusiqueMaterializationCase
) -> ExperimentCaseResponse:
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
    return ExperimentCaseReferenceResponse(
        experiment_id=experiment_id,
        case_id=case.case_id,
        question=case.question,
        gold_answer=case.answer,
        answer_aliases=case.answer_aliases,
        hop_count=case.hop_count,
        answerable=case.answerable,
        gold_support_indices=(case.gold_support_indices),
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
