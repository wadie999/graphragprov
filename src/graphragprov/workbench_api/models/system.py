"""System capability resources."""

from pydantic import BaseModel


class Capabilities(BaseModel):
    artifact_browser: bool = True
    graph_queries: bool
    provenance_rewrite: bool
    natural_language_planner: bool


class Health(BaseModel):
    status: str = "ok"
