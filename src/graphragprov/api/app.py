"""FastAPI application factory."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as distribution_version

from fastapi import FastAPI

from graphragprov.api.router import router

_APPLICATION_TITLE = "GraphRAGProv API"
_APPLICATION_DESCRIPTION = (
    "HTTP interface for grounded graph extraction, "
    "multi-hop question answering, and exact provenance."
)


def create_app() -> FastAPI:
    """Create one independently configurable FastAPI application."""

    application = FastAPI(
        title=_APPLICATION_TITLE,
        description=_APPLICATION_DESCRIPTION,
        version=_package_version(),
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
