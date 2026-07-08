"""Construction and deterministic serialization of grounded RDF datasets."""

from collections.abc import Iterable

from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD

from graphragprov.domain.source_unit import SourceUnit
from graphragprov.extraction.result import ExtractionResult
from graphragprov.extraction.span import TextSpan
from graphragprov.rdf.provenance import (
    canonical_evidence,
    canonical_occurrence_bytes,
    occurrence_token,
)
from graphragprov.rdf.terms import (
    occurrence_iri,
    rdf_triple,
    span_iri,
    unit_graph_iri,
)
from graphragprov.rdf.vocabulary import GP


def build_extraction_dataset(
    source: SourceUnit,
    extraction: ExtractionResult,
) -> Dataset:
    """Build one named RDF graph from one validated extraction."""

    extraction.validate_against(source)

    dataset = Dataset()
    graph_iri = unit_graph_iri(source.unit_id)
    graph = dataset.graph(graph_iri)

    _add_source_unit(graph, graph_iri, source)

    canonical_by_token: dict[str, bytes] = {}

    for statement in extraction.statements:
        token = occurrence_token(
            unit_id=source.unit_id,
            statement=statement,
        )
        canonical_occurrence = canonical_occurrence_bytes(
            unit_id=source.unit_id,
            statement=statement,
        )

        existing_occurrence = canonical_by_token.get(token)

        if existing_occurrence is not None and existing_occurrence != canonical_occurrence:
            raise ValueError("provenance token collision between distinct grounded occurrences")

        canonical_by_token[token] = canonical_occurrence

        subject, predicate, object_ = rdf_triple(statement)
        occurrence = occurrence_iri(
            unit_id=source.unit_id,
            statement=statement,
        )

        graph.add((subject, predicate, object_))

        graph.add(
            (
                occurrence,
                RDF.type,
                GP.GroundedStatementOccurrence,
            )
        )
        graph.add((occurrence, RDF.subject, subject))
        graph.add((occurrence, RDF.predicate, predicate))
        graph.add((occurrence, RDF.object, object_))
        graph.add((occurrence, GP.sourceUnit, graph_iri))
        graph.add((occurrence, GP.provenanceToken, Literal(token)))

        _add_evidence(
            graph=graph,
            occurrence=occurrence,
            evidence_predicate=GP.subjectEvidence,
            evidence=statement.subject.evidence,
            unit_id=source.unit_id,
            graph_iri=graph_iri,
        )
        _add_evidence(
            graph=graph,
            occurrence=occurrence,
            evidence_predicate=GP.predicateEvidence,
            evidence=statement.predicate.evidence,
            unit_id=source.unit_id,
            graph_iri=graph_iri,
        )
        _add_evidence(
            graph=graph,
            occurrence=occurrence,
            evidence_predicate=GP.objectEvidence,
            evidence=statement.object.evidence,
            unit_id=source.unit_id,
            graph_iri=graph_iri,
        )

    return dataset


def serialize_extraction_trig(
    source: SourceUnit,
    extraction: ExtractionResult,
) -> str:
    """Serialize one extraction to deterministic, parseable TriG."""

    dataset = build_extraction_dataset(source, extraction)
    graph_iri = unit_graph_iri(source.unit_id)
    graph = dataset.graph(graph_iri)

    lines = sorted(
        f"{subject.n3()} {predicate.n3()} {object_.n3()} ." for subject, predicate, object_ in graph
    )

    body = "\n".join(f"    {line}" for line in lines)

    return f"GRAPH {graph_iri.n3()} {{\n{body}\n}}\n"


def _add_source_unit(
    graph: Graph,
    graph_iri: URIRef,
    source: SourceUnit,
) -> None:
    graph.add((graph_iri, RDF.type, GP.SourceUnit))
    graph.add((graph_iri, GP.unitId, Literal(source.unit_id)))
    graph.add((graph_iri, GP.title, Literal(source.title)))
    graph.add((graph_iri, GP.text, Literal(source.text)))


def _add_evidence(
    *,
    graph: Graph,
    occurrence: URIRef,
    evidence_predicate: URIRef,
    evidence: Iterable[TextSpan],
    unit_id: str,
    graph_iri: URIRef,
) -> None:
    for span in canonical_evidence(evidence):
        span_resource = span_iri(
            unit_id=unit_id,
            span=span,
        )

        graph.add((occurrence, evidence_predicate, span_resource))
        graph.add((span_resource, RDF.type, GP.TextSpan))
        graph.add((span_resource, GP.sourceUnit, graph_iri))
        graph.add((span_resource, GP.segment, Literal(span.segment.value)))
        graph.add(
            (
                span_resource,
                GP.start,
                Literal(
                    span.start,
                    datatype=XSD.nonNegativeInteger,
                    normalize=False,
                ),
            )
        )
        graph.add(
            (
                span_resource,
                GP.end,
                Literal(
                    span.end,
                    datatype=XSD.nonNegativeInteger,
                    normalize=False,
                ),
            )
        )
        graph.add((span_resource, GP.quote, Literal(span.quote)))
