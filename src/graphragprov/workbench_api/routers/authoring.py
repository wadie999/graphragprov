"""Writable endpoints for user-created workbench experiments."""

from fastapi import APIRouter, HTTPException

from graphragprov.workbench_api.dependencies import ServiceDep
from graphragprov.workbench_api.models import (
    CaseSnapshot,
    CaseSummary,
    ExperimentSummary,
    GraphBuildRequest,
    WorkspaceCaseCreate,
    WorkspaceExperimentCreate,
    WorkspaceSourcesUpdate,
)

router = APIRouter(
    prefix="/api/v1/workspace",
    tags=["workspace"],
)


@router.post(
    "/experiments",
    response_model=ExperimentSummary,
)
def create_experiment(
    request: WorkspaceExperimentCreate,
    svc: ServiceDep,
) -> ExperimentSummary:
    try:
        return (
            svc.user_workspace.create_experiment(
                request.name
            )
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error


@router.post(
    "/experiments/{experiment_id}/cases",
    response_model=CaseSummary,
)
def create_case(
    experiment_id: str,
    request: WorkspaceCaseCreate,
    svc: ServiceDep,
) -> CaseSummary:
    try:
        return (
            svc.user_workspace.create_case(
                experiment_id,
                request.name,
            )
        )
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error


@router.put(
    (
        "/experiments/{experiment_id}"
        "/cases/{case_id}/sources"
    ),
    response_model=CaseSnapshot,
)
def update_sources(
    experiment_id: str,
    case_id: str,
    request: WorkspaceSourcesUpdate,
    svc: ServiceDep,
) -> CaseSnapshot:
    try:
        return (
            svc.user_workspace.update_sources(
                experiment_id,
                case_id,
                request.sources,
            )
        )
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error


@router.post(
    (
        "/experiments/{experiment_id}"
        "/cases/{case_id}/builds"
    ),
    response_model=CaseSnapshot,
)
def build_case(
    experiment_id: str,
    case_id: str,
    request: GraphBuildRequest,
    svc: ServiceDep,
) -> CaseSnapshot:
    try:
        return (
            svc.user_workspace.build_case(
                experiment_id,
                case_id,
                mode=request.mode,
                question=request.question,
            )
        )
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error