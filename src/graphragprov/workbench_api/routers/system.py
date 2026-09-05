"""Workbench health and capability endpoints."""

from fastapi import APIRouter

from graphragprov.workbench_api.dependencies import ServiceDep
from graphragprov.workbench_api.models import Capabilities, Health

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/health", response_model=Health)
def health() -> Health:
    return Health()


@router.get("/capabilities", response_model=Capabilities)
def capabilities(svc: ServiceDep) -> Capabilities:
    return Capabilities(
        graph_queries=bool(svc.config.graphdb.base_url),
        provenance_rewrite=bool(svc.config.sparqlprov.base_url),
        natural_language_planner=svc.planner.available,
    )