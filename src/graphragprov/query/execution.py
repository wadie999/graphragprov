"""Execution of provenance-aware SPARQL queries."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from graphragprov.graphdb import GraphDBClient
from graphragprov.npcs import NPCSClient

PROVENANCE_VARIABLE = "finalprovennacevariable"

ProvenanceQueryStage = Literal["original_completed", "rewritten", "rewritten_completed"]

ProvenanceQueryEventSink = Callable[[ProvenanceQueryStage, dict[str, object]], None]


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

        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)


def execute_provenance_query(
    *,
    sparql: str,
    graphdb: GraphDBClient,
    npcs: NPCSClient,
    event_sink: ProvenanceQueryEventSink | None = None,
) -> ProvenanceQueryExecution:
    """Execute an original query and its NPCS rewrite against GraphDB."""

    if not sparql.strip():
        raise ValueError("SPARQL query must not be empty")

    original_result = graphdb.query(sparql)

    _emit(
        event_sink,
        "original_completed",
        {"original_query": sparql, "original_result": original_result},
    )

    rewritten_query = npcs.rewrite(sparql)

    _emit(event_sink, "rewritten", {"rewritten_query": rewritten_query})

    rewritten_result = graphdb.query(rewritten_query)

    _emit(
        event_sink,
        "rewritten_completed",
        {"rewritten_query": rewritten_query, "rewritten_result": rewritten_result},
    )

    return ProvenanceQueryExecution(
        original_query=sparql,
        original_result=original_result,
        rewritten_query=rewritten_query,
        rewritten_result=rewritten_result,
    )


def extract_provenance_polynomial(execution: ProvenanceQueryExecution) -> str:
    """Extract one non-empty NPCS polynomial from a rewritten result."""

    results = execution.rewritten_result.get("results")

    if not isinstance(results, dict):
        raise ValueError("rewritten query result has no results object")

    bindings = results.get("bindings")

    if not isinstance(bindings, list):
        raise ValueError("rewritten query result has no bindings list")

    if len(bindings) != 1:
        raise ValueError("rewritten provenance query must return exactly one binding")

    row = bindings[0]

    if not isinstance(row, dict):
        raise ValueError("rewritten query binding must be an object")

    provenance = row.get(PROVENANCE_VARIABLE)

    if not isinstance(provenance, dict):
        raise ValueError(f"rewritten query binding has no {PROVENANCE_VARIABLE!r} value")

    value = provenance.get("value")

    if not isinstance(value, str) or not value.strip():
        raise ValueError("provenance polynomial must be a non-empty string")

    return value


def _emit(
    event_sink: ProvenanceQueryEventSink | None,
    stage: ProvenanceQueryStage,
    payload: dict[str, object],
) -> None:
    if event_sink is not None:
        event_sink(stage, payload)
