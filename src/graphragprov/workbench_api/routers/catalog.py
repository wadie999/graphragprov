"""Experiment and case catalog endpoints."""

from fastapi import APIRouter, HTTPException

from graphragprov.workbench_api.dependencies import ServiceDep
from graphragprov.workbench_api.models import (
    CaseList,
    CaseSummary,
    ExperimentList,
    ExperimentSummary,
    MetricCollection,
)
from graphragprov.workbench_api.services.experiment_metrics import experiment_metrics

router = APIRouter(prefix="/api/v1", tags=["catalog"])


@router.get("/experiments", response_model=ExperimentList)
def list_experiments(svc: ServiceDep) -> ExperimentList:
    items = svc.snapshots.experiments()
    return ExperimentList(items=items, total=len(items))


@router.get("/experiments/{experiment_id}", response_model=ExperimentSummary)
def get_experiment(experiment_id: str, svc: ServiceDep) -> ExperimentSummary:
    for item in svc.snapshots.experiments():
        if item.experiment_id == experiment_id:
            return item
    raise HTTPException(status_code=404, detail="experiment not found")


@router.get("/experiments/{experiment_id}/cases", response_model=CaseList)
def list_cases(experiment_id: str, svc: ServiceDep) -> CaseList:
    try:
        items = svc.snapshots.cases(experiment_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return CaseList(experiment_id=experiment_id, items=items, total=len(items))


@router.get("/experiments/{experiment_id}/cases/{case_id}", response_model=CaseSummary)
def get_case(experiment_id: str, case_id: str, svc: ServiceDep) -> CaseSummary:
    try:
        snapshot = svc.snapshots.snapshot_for(experiment_id, case_id)
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return CaseSummary(
        experiment_id=experiment_id,
        case_id=case_id,
        snapshot_id=snapshot.snapshot_id,
        question=snapshot.benchmark.question,
        expected_answer=snapshot.benchmark.expected_answers[0]
        if snapshot.benchmark.expected_answers
        else "",
        hop_count=snapshot.benchmark.hop_count,
        artifact_status=snapshot.artifact_status,
        graph_available=snapshot.graph is not None,
        provenance_available=snapshot.reference_run is not None
        and bool(snapshot.reference_run.provenance),
    )


@router.get("/experiments/{experiment_id}/metrics", response_model=MetricCollection)
def get_experiment_metrics(experiment_id: str, svc: ServiceDep) -> MetricCollection:
    try:
        return experiment_metrics(svc.catalog, experiment_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
