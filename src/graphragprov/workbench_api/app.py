"""FastAPI application for the GraphRAGProv research workbench."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from graphragprov.workbench_api.config import WorkbenchConfig, load_config
from graphragprov.workbench_api.container import Services, build_services
from graphragprov.workbench_api.router import router


def create_app(
    *, config: WorkbenchConfig | None = None, services: Services | None = None
) -> FastAPI:
    resolved = config or load_config()
    application = FastAPI(
        title="GraphRAGProv Research Workbench",
        version="1.0",
        description="Immutable experiment inspection and interactive provenance-aware graph QA.",
    )
    application.state.services = services or build_services(resolved)
    application.include_router(router)
    _mount_frontend(application, resolved.frontend_dist)
    return application


def _mount_frontend(application: FastAPI, dist: Path) -> None:
    if dist.is_dir() and (dist / "index.html").exists():
        application.mount("/", StaticFiles(directory=dist, html=True), name="frontend")


app = create_app()
