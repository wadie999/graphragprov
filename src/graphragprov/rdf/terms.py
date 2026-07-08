"""Deterministic conversion from extracted values to RDF terms."""

from hashlib import sha256
from typing import TypeAlias
from urllib.parse import quote

from rdflib import Literal, URIRef
from rdflib.namespace import XSD

from graphragprov.extraction.span import TextSpan
from graphragprov.extraction.statement import GroundedStatement, LiteralDatatype
from graphragprov.hashing import validate_source_unit_id
from graphragprov.rdf.provenance import (
    occurrence_token,
    span_location_token,
)

ENTITY_NAMESPACE = "urn:graphragprov:entity:"
PREDICATE_NAMESPACE = "urn:graphragprov:predicate:"
UNIT_NAMESPACE = "urn:graphragprov:unit:"
OCCURRENCE_NAMESPACE = "urn:graphragprov:occurrence:"
SPAN_NAMESPACE = "urn:graphragprov:span:"

RdfObject: TypeAlias = URIRef | Literal
RdfTriple: TypeAlias = tuple[URIRef, URIRef, RdfObject]

_LITERAL_DATATYPES: dict[LiteralDatatype, URIRef] = {
    LiteralDatatype.STRING: XSD.string,
    LiteralDatatype.INTEGER: XSD.integer,
    LiteralDatatype.DECIMAL: XSD.decimal,
    LiteralDatatype.BOOLEAN: XSD.boolean,
    LiteralDatatype.YEAR: XSD.gYear,
    LiteralDatatype.YEAR_MONTH: XSD.gYearMonth,
    LiteralDatatype.DATE: XSD.date,
    LiteralDatatype.DATE_TIME: XSD.dateTime,
}


def entity_iri(value: str) -> URIRef:
    """Mint an entity IRI from the exact extracted entity value."""

    return URIRef(f"{ENTITY_NAMESPACE}{_encode_value(value)}")


def predicate_iri(value: str) -> URIRef:
    """Mint a predicate IRI from the exact extracted predicate value."""

    return URIRef(f"{PREDICATE_NAMESPACE}{_encode_value(value)}")


def unit_graph_iri(unit_id: str) -> URIRef:
    """Return the named-graph IRI of one complete source unit."""

    validate_source_unit_id(unit_id)
    return URIRef(f"{UNIT_NAMESPACE}{unit_id}")


def occurrence_iri(
    *,
    unit_id: str,
    statement: GroundedStatement,
) -> URIRef:
    """Return the compact IRI of one grounded statement occurrence."""

    token = occurrence_token(
        unit_id=unit_id,
        statement=statement,
    )
    digest = sha256(token.encode("utf-8")).hexdigest()

    return URIRef(f"{OCCURRENCE_NAMESPACE}{digest}")


def span_iri(
    *,
    unit_id: str,
    span: TextSpan,
) -> URIRef:
    """Return the deterministic IRI of one span in one source unit."""

    validate_source_unit_id(unit_id)

    return URIRef(f"{SPAN_NAMESPACE}{unit_id}:{span_location_token(span)}")


def statement_object(statement: GroundedStatement) -> RdfObject:
    """Convert the statement object into an entity IRI or typed literal."""

    if statement.object_datatype is None:
        return entity_iri(statement.object.value)

    return Literal(
        statement.object.value,
        datatype=_LITERAL_DATATYPES[statement.object_datatype],
        normalize=False,
    )


def rdf_triple(statement: GroundedStatement) -> RdfTriple:
    """Convert one grounded statement into its semantic RDF triple."""

    return (
        entity_iri(statement.subject.value),
        predicate_iri(statement.predicate.value),
        statement_object(statement),
    )


def _encode_value(value: str) -> str:
    if not value.strip():
        raise ValueError("RDF term value must not be empty")

    return quote(value, safe="")
