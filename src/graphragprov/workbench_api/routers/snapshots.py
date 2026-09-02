"""Immutable case snapshot endpoints."""

from fastapi import APIRouter, HTTPException

from graphragprov.workbench_api.dependencies import ServiceDep
from graphragprov.workbench_api.models import (
    BenchmarkRecord,
    CaseSnapshot,
    GraphSnapshot,
    MetricCollection,
    QueryRun,
    SourceUnitView,
)

router = APIRouter(prefix="/api/v1/snapshots", tags=["snapshots"])


def _snapshot(snapshot_id: str, svc: ServiceDep) -> CaseSnapshot:
    try:
        return svc.snapshots.snapshot(snapshot_id)
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/{snapshot_id}", response_model=CaseSnapshot)
def get_snapshot(snapshot_id: str, svc: ServiceDep) -> CaseSnapshot:
    return _snapshot(snapshot_id, svc)


@router.get("/{snapshot_id}/benchmark", response_model=BenchmarkRecord)
def get_benchmark(snapshot_id: str, svc: ServiceDep) -> BenchmarkRecord:
    benchmark = _snapshot(snapshot_id, svc).benchmark
    if benchmark is None:
        raise HTTPException(
            status_code=404,
            detail="snapshot has no benchmark ground truth",
        )
    return benchmark


@router.get(
    "/{snapshot_id}/sources",
    response_model=tuple[SourceUnitView, ...],
)
def get_sources(
    snapshot_id: str,
    svc: ServiceDep,
) -> tuple[SourceUnitView, ...]:
    return _snapshot(snapshot_id, svc).sources


@router.get("/{snapshot_id}/graph", response_model=GraphSnapshot)
def get_graph(snapshot_id: str, svc: ServiceDep) -> GraphSnapshot:
    graph = _snapshot(snapshot_id, svc).graph
    if graph is None:
        raise HTTPException(
            status_code=404,
            detail="snapshot has no frozen graph",
        )
    return graph


@router.get("/{snapshot_id}/metrics", response_model=MetricCollection)
def get_metrics(snapshot_id: str, svc: ServiceDep) -> MetricCollection:
    return _snapshot(snapshot_id, svc).metrics


@router.get("/{snapshot_id}/reference-run", response_model=QueryRun)
def get_reference_run(snapshot_id: str, svc: ServiceDep) -> QueryRun:
    run = _snapshot(snapshot_id, svc).reference_run
    if run is None:
        raise HTTPException(
            status_code=404,
            detail="snapshot has no reference execution",
        )
    return run