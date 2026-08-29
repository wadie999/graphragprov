"""Project persisted grounded extractions into stable graph resources."""

from graphragprov.workbench_api.artifacts import ArtifactCase
from graphragprov.workbench_api.models.graph import GraphEdge, GraphNode, GraphSnapshot
from graphragprov.workbench_api.services.graph_occurrences import project_occurrences
from graphragprov.workbench_api.services.graph_terms import (
    iri_node,
    ntriple,
    object_node,
    predicate_label,
    stable_id,
)


def project_graph(snapshot_id: str, artifact: ArtifactCase) -> GraphSnapshot | None:
    triples = _triples(artifact)
    if triples is None:
        return None
    occurrences = project_occurrences(artifact)
    by_signature: dict[tuple[str, ...], list[str]] = {}
    for triple_signature, occurrence in occurrences:
        by_signature.setdefault(triple_signature, []).append(occurrence.occurrence_id)
    nodes: dict[str, GraphNode] = {}
    edges: dict[str, GraphEdge] = {}
    lines: set[str] = set()
    for raw in triples:
        subject = str(raw.get("subject_iri", ""))
        predicate = str(raw.get("predicate_iri", ""))
        kind = str(raw.get("object_type", ""))
        value = str(raw.get("object_value", ""))
        datatype = _optional_str(raw.get("object_datatype"))
        language = _optional_str(raw.get("object_language"))
        triple_signature = (subject, predicate, kind, value, datatype or "", language or "")
        subject_node = iri_node(subject)
        target_node = object_node(kind, value, datatype, language)
        nodes[subject_node.node_id] = subject_node
        nodes[target_node.node_id] = target_node
        edge_id = stable_id("e", "\0".join(triple_signature))
        edges[edge_id] = GraphEdge(
            edge_id=edge_id,
            subject_node_id=subject_node.node_id,
            predicate_iri=predicate,
            predicate_label=predicate_label(predicate),
            object_node_id=target_node.node_id,
            occurrence_ids=tuple(by_signature.get(triple_signature, ())),
        )
        lines.add(ntriple(subject, predicate, kind, value, datatype, language))
    return GraphSnapshot(
        graph_id=stable_id("g", snapshot_id),
        nodes=tuple(nodes.values()),
        edges=tuple(edges.values()),
        occurrences=tuple(item for _, item in occurrences),
        ntriples="\n".join(sorted(lines)),
    )


def _triples(artifact: ArtifactCase) -> list[dict[str, object]] | None:
    if artifact.observation is None:
        return None
    raw = artifact.observation.get("triples")
    if not isinstance(raw, list):
        return None
    return [item for item in raw if isinstance(item, dict)]


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
