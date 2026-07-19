"""Read-only HTTP resources for materialized experiments."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from graphragprov.api.dependencies import ExperimentRepositoryDependency
from graphragprov.experiments import (
    ExperimentNotFoundError,
    InvalidExperimentIdError,
    StoredMusiqueExperiment,
)

router = APIRouter(
    prefix="/api/v1/experiments",
    tags=["experiments"],
)


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


@router.get(
    "",
    response_model=ExperimentListResponse,
    summary="List materialized experiments",
)
def list_experiments(
    repository: ExperimentRepositoryDependency,
) -> ExperimentListResponse:
    """Return all validated experiments available to the API."""

    experiments = repository.list_experiments()
    items = tuple(_to_experiment_response(experiment) for experiment in experiments)

    return ExperimentListResponse(
        items=items,
        total=len(items),
    )


@router.get(
    "/{experiment_id}",
    response_model=ExperimentResponse,
    summary="Get a materialized experiment",
)
def get_experiment(
    experiment_id: str,
    repository: ExperimentRepositoryDependency,
) -> ExperimentResponse:
    """Return public metadata for one validated experiment."""

    try:
        experiment = repository.get_experiment(experiment_id)
    except InvalidExperimentIdError as error:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_experiment_id",
                "message": str(error),
            },
        ) from error
    except ExperimentNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "experiment_not_found",
                "message": str(error),
            },
        ) from error

    return _to_experiment_response(experiment)


def _to_experiment_response(
    experiment: StoredMusiqueExperiment,
) -> ExperimentResponse:
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
        successful_extraction_count=manifest.successful_extraction_count,
        failed_extraction_count=manifest.failed_extraction_count,
        materialized_source_count=manifest.materialization.source_count,
        statement_count=manifest.materialization.statement_count,
    )