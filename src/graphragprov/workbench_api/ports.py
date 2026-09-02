"""Small structural interfaces at external-service boundaries."""

from contextlib import AbstractContextManager
from typing import Protocol

from graphragprov.workbench_api.artifacts import ArtifactCase


class GraphQueryBackend(Protocol):
    def query(self, sparql: str) -> dict[str, object]: ...


class ProvenanceRewriter(Protocol):
    def rewrite(self, sparql: str) -> str: ...


class SnapshotWorkspace(Protocol):
    def materialized(self, artifact: ArtifactCase) -> AbstractContextManager[GraphQueryBackend]: ...
