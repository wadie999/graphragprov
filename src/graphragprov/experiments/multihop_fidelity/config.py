"""Configuration for multi-hop fidelity experiments."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ArtifactOrigin(StrEnum):
    """How an experimental graph or query artifact was produced."""

    REFERENCE = "reference"
    LEARNED = "learned"


class QueryScope(StrEnum):
    """Dataset scope used when executing a semantic query."""

    SUPPORT = "support"
    REPOSITORY = "repository"


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    """Configuration shared by the multi-hop fidelity experiments."""

    graph_origin: ArtifactOrigin
    query_origin: ArtifactOrigin
    query_scope: QueryScope = QueryScope.SUPPORT
    max_source_attempts: int = 3
    max_query_attempts: int = 5

    def __post_init__(self) -> None:
        if self.max_source_attempts < 1:
            raise ValueError("max_source_attempts must be at least 1")

        if self.max_query_attempts < 1:
            raise ValueError("max_query_attempts must be at least 1")
