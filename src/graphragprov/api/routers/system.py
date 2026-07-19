"""System-level API endpoints."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    """Liveness status returned by the API."""

    status: Literal["ok"] = "ok"


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check API liveness",
)
def read_health() -> HealthResponse:
    """Confirm that the HTTP process is running."""

    return HealthResponse()
