"""GraphDB-compatible TriG-star serialization."""

from rdflib import Literal

from graphragprov.domain.source_unit import SourceUnit
from graphragprov.extraction.result import ExtractionResult
from graphragprov.rdf.dataset import build_extraction_dataset
from graphragprov.rdf.provenance import occurrence_token
from graphragprov.rdf.terms import rdf_triple, unit_graph_iri
from graphragprov.rdf.vocabulary import GP


def serialize_extraction_trig_star(
    source: SourceUnit,
    extraction: ExtractionResult,
) -> str:
    """Serialize one grounded extraction as deterministic TriG-star.

    The output preserves the complete standard RDF representation and adds
    one RDF-star occurrence annotation for each distinct grounded statement.
    """

    dataset = build_extraction_dataset(source, extraction)
    graph_iri = unit_graph_iri(source.unit_id)
    graph = dataset.graph(graph_iri)

    lines = {
        f"{subject.n3()} {predicate.n3()} {object_.n3()} ." for subject, predicate, object_ in graph
    }

    for statement in extraction.statements:
        subject, predicate, object_ = rdf_triple(statement)
        token = occurrence_token(
            unit_id=source.unit_id,
            statement=statement,
        )

        lines.add(
            f"<< {subject.n3()} {predicate.n3()} {object_.n3()} >> "
            f"{GP.occurrenceOf.n3()} {Literal(token).n3()} ."
        )

    body = "\n".join(f"    {line}" for line in sorted(lines))

    return f"GRAPH {graph_iri.n3()} {{\n{body}\n}}\n"
