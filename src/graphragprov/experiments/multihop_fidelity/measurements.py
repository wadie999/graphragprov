"""Measurements for multi-hop fidelity graph construction."""

from __future__ import annotations

from dataclasses import dataclass

from rdflib import BNode, Graph, Literal, URIRef

from graphragprov.experiments.multihop_fidelity.graph import ReferenceGraphExtractionResult
from graphragprov.metrics import measure_source_coverage
from graphragprov.rdf.terms import ENTITY_NAMESPACE


@dataclass(frozen=True, slots=True)
class SourceExtractionMeasurements:
    """Measurements for one successfully extracted supporting source."""

    paragraph_index: int
    unit_id: str
    title_character_count: int
    text_character_count: int
    statement_occurrence_count: int
    correction_attempted: bool
    initial_rejection_count: int
    corrected_valid_statement_count: int
    remaining_rejection_count: int
    coverage: dict[str, object]

    def __post_init__(self) -> None:
        counts = (
            self.title_character_count,
            self.text_character_count,
            self.statement_occurrence_count,
            self.initial_rejection_count,
            self.corrected_valid_statement_count,
            self.remaining_rejection_count,
        )

        if any(count < 0 for count in counts):
            raise ValueError("source measurement counts must not be negative")

        if not self.unit_id.strip():
            raise ValueError("source unit ID must not be empty")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable representation."""

        return {
            "paragraph_index": self.paragraph_index,
            "unit_id": self.unit_id,
            "title_character_count": self.title_character_count,
            "text_character_count": self.text_character_count,
            "statement_occurrence_count": self.statement_occurrence_count,
            "correction_attempted": self.correction_attempted,
            "initial_rejection_count": self.initial_rejection_count,
            "corrected_valid_statement_count": self.corrected_valid_statement_count,
            "remaining_rejection_count": self.remaining_rejection_count,
            "coverage": self.coverage,
        }


@dataclass(frozen=True, slots=True)
class ReferenceExtractionMeasurements:
    """Aggregate extraction measurements for one reference graph."""

    sources: tuple[SourceExtractionMeasurements, ...]
    source_count: int
    title_character_count: int
    text_character_count: int
    statement_occurrence_count: int
    whole_source_attempt_count: int
    whole_source_retry_count: int
    targeted_correction_count: int
    initial_rejection_count: int
    corrected_valid_statement_count: int
    remaining_rejection_count: int

    def __post_init__(self) -> None:
        counts = (
            self.source_count,
            self.title_character_count,
            self.text_character_count,
            self.statement_occurrence_count,
            self.whole_source_attempt_count,
            self.whole_source_retry_count,
            self.targeted_correction_count,
            self.initial_rejection_count,
            self.corrected_valid_statement_count,
            self.remaining_rejection_count,
        )

        if any(count < 0 for count in counts):
            raise ValueError("reference extraction measurement counts must not be negative")

        if self.source_count != len(self.sources):
            raise ValueError("source count must equal the number of source measurements")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable representation."""

        return {
            "sources": [source.to_dict() for source in self.sources],
            "source_count": self.source_count,
            "title_character_count": self.title_character_count,
            "text_character_count": self.text_character_count,
            "statement_occurrence_count": self.statement_occurrence_count,
            "whole_source_attempt_count": self.whole_source_attempt_count,
            "whole_source_retry_count": self.whole_source_retry_count,
            "targeted_correction_count": self.targeted_correction_count,
            "initial_rejection_count": self.initial_rejection_count,
            "corrected_valid_statement_count": self.corrected_valid_statement_count,
            "remaining_rejection_count": self.remaining_rejection_count,
        }


@dataclass(frozen=True, slots=True)
class FrozenGraphMeasurements:
    """Structural measurements of the frozen semantic RDF graph."""

    named_graph_count: int
    semantic_triple_count: int
    resource_node_count: int
    entity_node_count: int
    literal_value_count: int
    predicate_count: int

    def __post_init__(self) -> None:
        counts = (
            self.named_graph_count,
            self.semantic_triple_count,
            self.resource_node_count,
            self.entity_node_count,
            self.literal_value_count,
            self.predicate_count,
        )

        if any(count < 0 for count in counts):
            raise ValueError("frozen graph measurement counts must not be negative")

    def to_dict(self) -> dict[str, int]:
        """Return a deterministic JSON-serializable representation."""

        return {
            "named_graph_count": self.named_graph_count,
            "semantic_triple_count": self.semantic_triple_count,
            "resource_node_count": self.resource_node_count,
            "entity_node_count": self.entity_node_count,
            "literal_value_count": self.literal_value_count,
            "predicate_count": self.predicate_count,
        }


def measure_reference_extractions(
    result: ReferenceGraphExtractionResult,
) -> ReferenceExtractionMeasurements:
    """Measure successful H0 grounded extractions.

    Existing source-coverage metrics remain authoritative for textual coverage.
    This function only composes them with experiment-level counts.
    """

    source_measurements: list[SourceExtractionMeasurements] = []

    for item in result.items:
        run = item.run
        correction = run.correction

        coverage = measure_source_coverage(source=run.source, extraction=run.extraction).to_dict()

        source_measurements.append(
            SourceExtractionMeasurements(
                paragraph_index=item.paragraph_index,
                unit_id=run.source.unit_id,
                title_character_count=len(run.source.title),
                text_character_count=len(run.source.text),
                statement_occurrence_count=len(run.extraction.statements),
                correction_attempted=correction is not None,
                initial_rejection_count=(
                    0 if correction is None else len(correction.requested_rejections)
                ),
                corrected_valid_statement_count=(
                    0 if correction is None else correction.corrected_valid_statement_count
                ),
                remaining_rejection_count=(
                    0 if correction is None else len(correction.remaining_rejections)
                ),
                coverage=coverage,
            )
        )

    sources = tuple(source_measurements)

    return ReferenceExtractionMeasurements(
        sources=sources,
        source_count=len(sources),
        title_character_count=sum(source.title_character_count for source in sources),
        text_character_count=sum(source.text_character_count for source in sources),
        statement_occurrence_count=sum(source.statement_occurrence_count for source in sources),
        whole_source_attempt_count=result.attempt_count,
        whole_source_retry_count=result.retry_count,
        targeted_correction_count=sum(source.correction_attempted for source in sources),
        initial_rejection_count=sum(source.initial_rejection_count for source in sources),
        corrected_valid_statement_count=sum(
            source.corrected_valid_statement_count for source in sources
        ),
        remaining_rejection_count=sum(source.remaining_rejection_count for source in sources),
    )


def measure_frozen_graph(graph_ntriples: str, *, named_graph_count: int) -> FrozenGraphMeasurements:
    """Measure the exact semantic RDF graph exposed to query construction.

    N-Triples are parsed with RDFLib so duplicate serialized triples collapse
    according to RDF graph set semantics.

    Provenance annotations are intentionally absent because the caller supplies
    the semantic graph observation, not the RDF-star provenance representation.
    """

    if named_graph_count < 0:
        raise ValueError("named graph count must not be negative")

    graph = Graph()

    if graph_ntriples.strip():
        graph.parse(data=graph_ntriples, format="nt")

    resource_nodes: set[URIRef | BNode] = set()
    entity_nodes: set[URIRef] = set()
    literal_values: set[Literal] = set()
    predicates: set[URIRef] = set()

    for subject, predicate, object_value in graph:
        if isinstance(subject, (URIRef, BNode)):
            resource_nodes.add(subject)

        if isinstance(object_value, (URIRef, BNode)):
            resource_nodes.add(object_value)

        if isinstance(subject, URIRef) and str(subject).startswith(ENTITY_NAMESPACE):
            entity_nodes.add(subject)

        if isinstance(object_value, URIRef) and str(object_value).startswith(ENTITY_NAMESPACE):
            entity_nodes.add(object_value)

        if isinstance(object_value, Literal):
            literal_values.add(object_value)

        if isinstance(predicate, URIRef):
            predicates.add(predicate)

    return FrozenGraphMeasurements(
        named_graph_count=named_graph_count,
        semantic_triple_count=len(graph),
        resource_node_count=len(resource_nodes),
        entity_node_count=len(entity_nodes),
        literal_value_count=len(literal_values),
        predicate_count=len(predicates),
    )
