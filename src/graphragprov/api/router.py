"""Composition of all GraphRAGProv HTTP routers."""

from fastapi import APIRouter

from graphragprov.api.routers.experiments import router as experiments_router
from graphragprov.api.routers.system import router as system_router

router = APIRouter()
router.include_router(system_router)
router.include_router(experiments_router)