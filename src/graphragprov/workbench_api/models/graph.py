"""Frozen semantic graph resources."""

from pydantic import BaseModel

from graphragprov.workbench_api.models.source import EvidenceSpan


class GraphNode(BaseModel):
    node_id: str
    kind: str
    value: str
    label: str
    datatype: str | None = None
    language: str | None = None


class GraphEdge(BaseModel):
    edge_id: str
    subject_node_id: str
    predicate_iri: str
    predicate_label: str
    object_node_id: str
    occurrence_ids: tuple[str, ...]


class StatementOccurrence(BaseModel):
    occurrence_id: str
    token: str
    semantic_edge_id: str
    source_id: str
    subject_evidence: tuple[EvidenceSpan, ...]
    predicate_evidence: tuple[EvidenceSpan, ...]
    object_evidence: tuple[EvidenceSpan, ...]


class GraphSnapshot(BaseModel):
    graph_id: str
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    occurrences: tuple[StatementOccurrence, ...]
    ntriples: str
