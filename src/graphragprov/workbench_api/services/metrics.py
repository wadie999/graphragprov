"""Stable metric projection over evolving experiment artifacts."""

from statistics import fmean

from graphragprov.workbench_api.artifacts import ArtifactCase
from graphragprov.workbench_api.models.metrics import MetricCollection, MetricObservation


def project_metrics(artifact: ArtifactCase) -> MetricCollection:
    items: list[MetricObservation] = []
    graph = artifact.graph_measurements or {}
    extraction = artifact.extraction_measurements or {}
    _add(items, "graph.node_count", "Nodes", graph.get("resource_node_count"), "graph")
    _add(items, "graph.edge_count", "Edges", graph.get("semantic_triple_count"), "graph")
    _add(items, "graph.predicate_count", "Predicates", graph.get("predicate_count"), "graph")
    _add(
        items,
        "graph.occurrence_count",
        "Occurrences",
        extraction.get("statement_occurrence_count"),
        "graph",
    )
    _add(
        items,
        "grounding.initial_rejections",
        "Initial rejects",
        extraction.get("initial_rejection_count"),
        "case",
    )
    _add(
        items,
        "grounding.corrected",
        "Corrected",
        extraction.get("corrected_valid_statement_count"),
        "case",
    )
    _add(items, "query.attempt_count", "Query attempts", len(artifact.query_attempts), "case")
    text_coverage = _mean_coverage(extraction, "character_coverage", "text")
    sentence_coverage = _mean_coverage(extraction, "sentence_coverage", None)
    if text_coverage is not None:
        _add(items, "coverage.text.mean", "Text coverage", text_coverage, "case", "%")
    if sentence_coverage is not None:
        _add(items, "coverage.sentence.mean", "Sentence coverage", sentence_coverage, "case", "%")
    return MetricCollection(items=tuple(items))


def _mean_coverage(data: dict[str, object], family: str, segment: str | None) -> float | None:
    values: list[float] = []
    sources = data.get("sources")
    if not isinstance(sources, list):
        return None
    for source in sources:
        if not isinstance(source, dict):
            continue
        coverage = source.get("coverage")
        if not isinstance(coverage, dict):
            continue
        family_data = coverage.get(family)
        if not isinstance(family_data, dict):
            continue
        overall = family_data.get("overall")
        if segment is not None and isinstance(overall, dict):
            overall = overall.get(segment)
        if isinstance(overall, dict):
            ratio = overall.get("coverage_ratio")
            if isinstance(ratio, (int, float)):
                values.append(float(ratio) * 100.0)
    return fmean(values) if values else None


def _add(
    items: list[MetricObservation],
    key: str,
    label: str,
    value: object,
    scope: str,
    unit: str | None = None,
) -> None:
    if isinstance(value, (int, float, bool, str)):
        items.append(MetricObservation(key=key, label=label, value=value, scope=scope, unit=unit))
