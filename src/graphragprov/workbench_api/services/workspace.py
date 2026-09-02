"""Disposable GraphDB workspace materialized from immutable artifacts."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock

from graphragprov.graphdb import GraphDBClient, materialize_grounded_extractions
from graphragprov.rdf.terms import unit_graph_iri
from graphragprov.workbench_api.artifacts import ArtifactCase


class GraphWorkspaceManager:
    def __init__(self, graphdb: GraphDBClient) -> None:
        self._graphdb = graphdb
        self._lock = Lock()

    @property
    def graphdb(self) -> GraphDBClient:
        return self._graphdb

    @contextmanager
    def materialized(self, artifact: ArtifactCase) -> Iterator[GraphDBClient]:
        if not artifact.extraction_runs:
            raise ValueError("selected artifact has no grounded graph extraction")
        with self._lock:
            for run in artifact.extraction_runs:
                graph_iri = unit_graph_iri(run.source.unit_id)
                self._graphdb.update(f"CLEAR GRAPH {graph_iri.n3()}")
            materialize_grounded_extractions(artifact.extraction_runs, graphdb=self._graphdb)
            yield self._graphdb
