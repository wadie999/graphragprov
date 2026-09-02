"""Natural-language planning and interactive SPARQL execution endpoints."""

from fastapi import APIRouter, HTTPException

from graphragprov.workbench_api.dependencies import ServiceDep
from graphragprov.workbench_api.models import (
    InteractiveQueryRequest,
    QueryPlan,
    QueryPlanRequest,
    QueryRun,
    QueryRunRequest,
)
from graphragprov.workbench_api.services.graph_projection import project_graph

router = APIRouter(prefix="/api/v1", tags=["execution"])


@router.post("/snapshots/{snapshot_id}/query-plans", response_model=QueryPlan)
def create_plan(snapshot_id: str, request: QueryPlanRequest, svc: ServiceDep) -> QueryPlan:
    try:
        snapshot = svc.snapshots.snapshot(snapshot_id)
        return svc.planner.create(snapshot, request.question)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/query-plans/{plan_id}", response_model=QueryPlan)
def get_plan(plan_id: str, svc: ServiceDep) -> QueryPlan:
    try:
        return svc.store.plan(plan_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="query plan not found") from error


@router.post("/snapshots/{snapshot_id}/query-runs", response_model=QueryRun)
def create_run(snapshot_id: str, request: QueryRunRequest, svc: ServiceDep) -> QueryRun:
    try:
        artifact = svc.snapshots.artifact(snapshot_id)
        graph = project_graph(snapshot_id, artifact)

        if graph is None:
            raise ValueError("snapshot has no frozen graph")

        return svc.executor.run(
            snapshot_id=snapshot_id, artifact=artifact, graph=graph, request=request
        )

    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/snapshots/{snapshot_id}/interactive-runs", response_model=QueryRun)
def create_interactive_run(
    snapshot_id: str, request: InteractiveQueryRequest, svc: ServiceDep
) -> QueryRun:
    try:
        artifact = svc.snapshots.artifact(snapshot_id)
        graph = project_graph(snapshot_id, artifact)

        if graph is None:
            raise ValueError("snapshot has no frozen graph")

        return svc.executor.run_interactive(
            snapshot_id=snapshot_id, artifact=artifact, graph=graph, request=request
        )

    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/query-runs/{run_id}", response_model=QueryRun)
def get_run(run_id: str, svc: ServiceDep) -> QueryRun:
    try:
        return svc.store.run(run_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="query run not found") from error


@router.get("/snapshots/{snapshot_id}/query-runs", response_model=tuple[QueryRun, ...])
def list_runs(snapshot_id: str, svc: ServiceDep) -> tuple[QueryRun, ...]:
    return svc.store.runs_for(snapshot_id)
