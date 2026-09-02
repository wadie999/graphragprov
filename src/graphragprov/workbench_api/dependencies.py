"""FastAPI dependency helpers."""

from typing import Annotated, cast

from fastapi import Depends, Request

from graphragprov.workbench_api.container import Services


def services(request: Request) -> Services:
    return cast(Services, request.app.state.services)


ServiceDep = Annotated[Services, Depends(services)]


__all__ = ["ServiceDep", "services"]
