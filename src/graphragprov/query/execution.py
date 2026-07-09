"""Execution of provenance-aware SPARQL queries."""

from __future__ import annotations

import json
from dataclasses import dataclass

from graphragprov.graphdb import GraphDBClient
from graphragprov.npcs import NPCSClient


@dataclass(frozen=True)
class ProvenanceQueryExecution:
    """Complete record of one original and provenance-rewritten query."""

    original_query: str
    original_result: dict[str, object]
    rewritten_query: str
    rewritten_result: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable execution record."""

        return {
            "original_query": self.original_query,
            "original_result": self.original_result,
            "rewritten_query": self.rewritten_query,
            "rewritten_result": self.rewritten_result,
        }

    def to_json(self) -> str:
        """Serialize the complete execution record deterministically."""

        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )


def execute_provenance_query(
    *,
    sparql: str,
    graphdb: GraphDBClient,
    npcs: NPCSClient,
) -> ProvenanceQueryExecution:
    """Execute an original query and its NPCS rewrite against GraphDB."""

    if not sparql.strip():
        raise ValueError("SPARQL query must not be empty")

    original_result = graphdb.query(sparql)
    rewritten_query = npcs.rewrite(sparql)
    rewritten_result = graphdb.query(rewritten_query)

    return ProvenanceQueryExecution(
        original_query=sparql,
        original_result=original_result,
        rewritten_query=rewritten_query,
        rewritten_result=rewritten_result,
    )
