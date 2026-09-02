"""Top-level workbench API router."""

from fastapi import APIRouter

from graphragprov.workbench_api.routers.authoring import router as authoring_router
from graphragprov.workbench_api.routers.catalog import router as catalog_router
from graphragprov.workbench_api.routers.execution import router as execution_router
from graphragprov.workbench_api.routers.resources import router as resources_router
from graphragprov.workbench_api.routers.snapshots import router as snapshots_router
from graphragprov.workbench_api.routers.system import router as system_router

router = APIRouter()

router.include_router(catalog_router)
router.include_router(snapshots_router)
router.include_router(resources_router)
router.include_router(execution_router)
router.include_router(authoring_router)
router.include_router(system_router)