"""FastAPI application factory."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as distribution_version
from pathlib import Path

from fastapi import FastAPI

from graphragprov.api.router import router
from graphragprov.experiments import (
    FilesystemMusiqueExperimentRepository,
    MusiqueExperimentRepository,
)

_APPLICATION_TITLE = "GraphRAGProv API"
_APPLICATION_DESCRIPTION = (
    "HTTP interface for grounded graph extraction, "
    "multi-hop question answering, and exact provenance."
)


def create_app(*, experiment_repository: MusiqueExperimentRepository | None = None) -> FastAPI:
    """Create one independently configurable FastAPI application."""

    application = FastAPI(
        title=_APPLICATION_TITLE, description=_APPLICATION_DESCRIPTION, version=_package_version()
    )

    application.state.experiment_repository = (
        experiment_repository
        if experiment_repository is not None
        else FilesystemMusiqueExperimentRepository(Path("runs"))
    )

    application.include_router(router)

    return application


def _package_version() -> str:
    """Return the installed package version."""

    try:
        return distribution_version("graphragprov")
    except PackageNotFoundError:
        return "0+unknown"


app = create_app()
