"""Individually addressable immutable snapshot resources."""

from fastapi import APIRouter, HTTPException

from graphragprov.workbench_api.container import Services
from graphragprov.workbench_api.dependencies import ServiceDep
from graphragprov.workbench_api.models import (
    CaseSnapshot,
    GraphEdge,
    GraphNode,
    SourceUnitView,
    StatementOccurrence,
)

router = APIRouter(prefix="/api/v1/snapshots", tags=["resources"])


def _snapshot(snapshot_id: str, svc: Services) -> CaseSnapshot:
    try:
        return svc.snapshots.snapshot(snapshot_id)
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/{snapshot_id}/sources/{source_id}", response_model=SourceUnitView)
def source(snapshot_id: str, source_id: str, svc: ServiceDep) -> SourceUnitView:
    snapshot = _snapshot(snapshot_id, svc)

    for item in snapshot.sources:
        if item.source_id == source_id:
            return item

    raise HTTPException(status_code=404, detail="source not found")


@router.get("/{snapshot_id}/graph/nodes/{node_id}", response_model=GraphNode)
def node(snapshot_id: str, node_id: str, svc: ServiceDep) -> GraphNode:
    graph = _snapshot(snapshot_id, svc).graph

    if graph is None:
        raise HTTPException(status_code=404, detail="snapshot has no frozen graph")

    for item in graph.nodes:
        if item.node_id == node_id:
            return item

    raise HTTPException(status_code=404, detail="node not found")


@router.get("/{snapshot_id}/graph/edges/{edge_id}", response_model=GraphEdge)
def edge(snapshot_id: str, edge_id: str, svc: ServiceDep) -> GraphEdge:
    graph = _snapshot(snapshot_id, svc).graph

    if graph is None:
        raise HTTPException(status_code=404, detail="snapshot has no frozen graph")

    for item in graph.edges:
        if item.edge_id == edge_id:
            return item

    raise HTTPException(status_code=404, detail="edge not found")


@router.get("/{snapshot_id}/occurrences/{occurrence_id}", response_model=StatementOccurrence)
def occurrence(snapshot_id: str, occurrence_id: str, svc: ServiceDep) -> StatementOccurrence:
    graph = _snapshot(snapshot_id, svc).graph

    if graph is None:
        raise HTTPException(status_code=404, detail="snapshot has no frozen graph")

    for item in graph.occurrences:
        if item.occurrence_id == occurrence_id:
            return item

    raise HTTPException(status_code=404, detail="occurrence not found")
