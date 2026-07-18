"""Materialization of grounded extractions in GraphDB."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from graphragprov.extraction.run import GroundedExtractionRun
from graphragprov.rdf.star import serialize_extraction_trig_star
from graphragprov.rdf.terms import unit_graph_iri


class TriGStarUploader(Protocol):
    """Minimal upload contract required by graph materialization."""

    def upload_trig_star(
        self,
        content: str | bytes,
    ) -> None:
        """Upload one TriG-star document."""


@dataclass(frozen=True, slots=True)
class GraphMaterializationSummary:
    """Deterministic summary of one graph materialization."""

    source_count: int
    statement_count: int
    graph_iris: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "source_count": self.source_count,
            "statement_count": self.statement_count,
            "graph_iris": list(self.graph_iris),
        }


def materialize_grounded_extractions(
    runs: Iterable[GroundedExtractionRun],
    *,
    graphdb: TriGStarUploader,
) -> GraphMaterializationSummary:
    """Serialize and upload each unique grounded source extraction once.

    Uploads are performed sequentially. GraphDB RDF set semantics make
    rerunning a completed or partially completed materialization idempotent.
    """

    runs_by_unit_id: dict[
        str,
        GroundedExtractionRun,
    ] = {}

    graph_iris: list[str] = []
    statement_count = 0

    for run in runs:
        existing = runs_by_unit_id.get(run.source.unit_id)

        if existing is not None:
            if existing.source != run.source:
                raise ValueError("identical source-unit IDs refer to different source content")

            if existing.extraction != run.extraction:
                raise ValueError("one source unit has conflicting grounded extractions")

            continue

        run.extraction.validate_against(run.source)

        trig_star = serialize_extraction_trig_star(
            run.source,
            run.extraction,
        )

        graphdb.upload_trig_star(trig_star)

        runs_by_unit_id[run.source.unit_id] = run

        graph_iris.append(str(unit_graph_iri(run.source.unit_id)))

        statement_count += len(run.extraction.statements)

    return GraphMaterializationSummary(
        source_count=len(runs_by_unit_id),
        statement_count=statement_count,
        graph_iris=tuple(graph_iris),
    )
