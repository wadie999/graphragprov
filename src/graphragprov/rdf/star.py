"""Minimal GraphDB-compatible TriG-star serialization for NPCS."""

from rdflib import Literal

from graphragprov.domain.source_unit import SourceUnit
from graphragprov.extraction.result import ExtractionResult
from graphragprov.rdf.provenance import occurrence_token
from graphragprov.rdf.terms import rdf_triple, unit_graph_iri
from graphragprov.rdf.vocabulary import PROV


def serialize_extraction_trig_star(
    source: SourceUnit,
    extraction: ExtractionResult,
) -> str:
    """Serialize RDF triples and their grounded provenance annotations."""

    extraction.validate_against(source)

    triples: set[str] = set()
    annotations: set[str] = set()

    for statement in extraction.statements:
        subject, predicate, object_ = rdf_triple(statement)

        triples.add(f"{subject.n3()} {predicate.n3()} {object_.n3()} .")

        token = occurrence_token(
            unit_id=source.unit_id,
            statement=statement,
        )

        annotations.add(
            f"<< {subject.n3()} {predicate.n3()} {object_.n3()} >> "
            f"textprov:occurrenceOf {Literal(token).n3()} ."
        )

    sections: list[str] = []

    if triples:
        sections.append("\n".join(f"    {triple}" for triple in sorted(triples)))

    if annotations:
        sections.append("\n".join(f"    {annotation}" for annotation in sorted(annotations)))

    body = "\n\n".join(sections)
    graph_iri = unit_graph_iri(source.unit_id)

    return f"@prefix textprov: <{PROV}> .\n\nGRAPH {graph_iri.n3()} {{\n{body}\n}}\n"
