import pytest
from rdflib import Literal, URIRef
from rdflib.namespace import XSD

from graphragprov.extraction.grounded_value import GroundedValue
from graphragprov.extraction.span import TextSegment, TextSpan
from graphragprov.extraction.statement import GroundedStatement, LiteralDatatype
from graphragprov.hashing import source_unit_id
from graphragprov.rdf.terms import (
    entity_iri,
    predicate_iri,
    rdf_triple,
    statement_object,
    unit_graph_iri,
)


def _evidence(quote: str) -> tuple[TextSpan, ...]:
    return (
        TextSpan(
            segment=TextSegment.TEXT,
            start=0,
            end=len(quote),
            quote=quote,
        ),
    )


def _statement(
    *,
    object_value: str = "London",
    datatype: LiteralDatatype | None = None,
) -> GroundedStatement:
    return GroundedStatement(
        subject=GroundedValue(
            value="Ada Lovelace",
            evidence=_evidence("Ada"),
        ),
        predicate=GroundedValue(
            value="bornIn",
            evidence=_evidence("born"),
        ),
        object=GroundedValue(
            value=object_value,
            evidence=_evidence(object_value),
        ),
        object_datatype=datatype,
    )


def test_entity_iri_is_deterministic_and_percent_encoded() -> None:
    assert entity_iri("S. A. Kenner") == URIRef("urn:graphragprov:entity:S.%20A.%20Kenner")
    assert entity_iri("S. A. Kenner") == entity_iri("S. A. Kenner")


def test_entity_and_predicate_namespaces_are_distinct() -> None:
    assert entity_iri("bornIn") != predicate_iri("bornIn")

    assert predicate_iri("bornIn") == URIRef("urn:graphragprov:predicate:bornIn")


def test_unit_graph_iri_contains_the_complete_source_unit_id() -> None:
    unit_id = source_unit_id(
        title="Ada Lovelace",
        text="She was born in London.",
    )

    assert unit_graph_iri(unit_id) == URIRef(f"urn:graphragprov:unit:{unit_id}")


def test_entity_object_becomes_an_entity_iri() -> None:
    statement = _statement()

    assert statement_object(statement) == entity_iri("London")

    assert rdf_triple(statement) == (
        entity_iri("Ada Lovelace"),
        predicate_iri("bornIn"),
        entity_iri("London"),
    )


@pytest.mark.parametrize(
    ("datatype", "value", "expected_iri"),
    [
        (LiteralDatatype.STRING, "Ada Lovelace", XSD.string),
        (LiteralDatatype.INTEGER, "2018", XSD.integer),
        (LiteralDatatype.DECIMAL, "2018.0", XSD.decimal),
        (LiteralDatatype.BOOLEAN, "true", XSD.boolean),
        (LiteralDatatype.YEAR, "2018", XSD.gYear),
        (LiteralDatatype.YEAR_MONTH, "2018-03", XSD.gYearMonth),
        (LiteralDatatype.DATE, "2018-03-06", XSD.date),
        (
            LiteralDatatype.DATE_TIME,
            "2018-03-06T12:30:00",
            XSD.dateTime,
        ),
    ],
)
def test_literal_objects_preserve_their_datatype(
    datatype: LiteralDatatype,
    value: str,
    expected_iri: URIRef,
) -> None:
    statement = _statement(
        object_value=value,
        datatype=datatype,
    )

    rdf_object = statement_object(statement)

    assert isinstance(rdf_object, Literal)
    assert str(rdf_object) == value
    assert rdf_object.datatype == expected_iri


def test_literal_and_entity_with_same_value_are_different_rdf_terms() -> None:
    entity_statement = _statement(object_value="2018")
    literal_statement = _statement(
        object_value="2018",
        datatype=LiteralDatatype.YEAR,
    )

    assert statement_object(entity_statement) != statement_object(literal_statement)


def test_abbreviated_unit_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="full 64-character"):
        unit_graph_iri("u_0a5e4e80")
