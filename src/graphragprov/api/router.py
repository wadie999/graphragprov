"""Composition of all GraphRAGProv HTTP routers."""

from fastapi import APIRouter

from graphragprov.api.routers.system import router as system_router

router = APIRouter()
router.include_router(system_router)
