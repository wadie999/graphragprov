from rdflib import Dataset, Literal
from rdflib.namespace import RDF, XSD

from graphragprov.domain.source_unit import SourceUnit
from graphragprov.extraction.grounded_value import GroundedValue
from graphragprov.extraction.result import ExtractionResult
from graphragprov.extraction.span import TextSegment, TextSpan
from graphragprov.extraction.statement import (
    GroundedStatement,
    LiteralDatatype,
)
from graphragprov.hashing import source_unit_id
from graphragprov.rdf.dataset import (
    build_extraction_dataset,
    serialize_extraction_trig,
)
from graphragprov.rdf.provenance import occurrence_token
from graphragprov.rdf.terms import (
    entity_iri,
    occurrence_iri,
    predicate_iri,
    span_iri,
    unit_graph_iri,
)
from graphragprov.rdf.vocabulary import GP


def _source(*, punctuation: str = ".") -> SourceUnit:
    title = "Ada Lovelace"
    text = f"She was born in London in 1815{punctuation}"

    return SourceUnit(
        unit_id=source_unit_id(title=title, text=text),
        title=title,
        text=text,
    )


def _subject() -> GroundedValue:
    return GroundedValue(
        value="Ada Lovelace",
        evidence=(
            TextSpan(
                segment=TextSegment.TITLE,
                start=0,
                end=12,
                quote="Ada Lovelace",
            ),
            TextSpan(
                segment=TextSegment.TEXT,
                start=0,
                end=3,
                quote="She",
            ),
        ),
    )


def _born_in_statement() -> GroundedStatement:
    return GroundedStatement(
        subject=_subject(),
        predicate=GroundedValue(
            value="bornIn",
            evidence=(
                TextSpan(
                    segment=TextSegment.TEXT,
                    start=8,
                    end=15,
                    quote="born in",
                ),
            ),
        ),
        object=GroundedValue(
            value="London",
            evidence=(
                TextSpan(
                    segment=TextSegment.TEXT,
                    start=16,
                    end=22,
                    quote="London",
                ),
            ),
        ),
    )


def _birth_year_statement() -> GroundedStatement:
    return GroundedStatement(
        subject=_subject(),
        predicate=GroundedValue(
            value="birthYear",
            evidence=(
                TextSpan(
                    segment=TextSegment.TEXT,
                    start=8,
                    end=12,
                    quote="born",
                ),
            ),
        ),
        object=GroundedValue(
            value="1815",
            evidence=(
                TextSpan(
                    segment=TextSegment.TEXT,
                    start=26,
                    end=30,
                    quote="1815",
                ),
            ),
        ),
        object_datatype=LiteralDatatype.YEAR,
    )


def _extraction(source: SourceUnit) -> ExtractionResult:
    return ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            _born_in_statement(),
            _birth_year_statement(),
        ),
    )


def test_dataset_contains_semantic_triples_and_grounded_occurrences() -> None:
    source = _source()
    extraction = _extraction(source)

    dataset = build_extraction_dataset(source, extraction)
    graph_iri = unit_graph_iri(source.unit_id)
    graph = dataset.graph(graph_iri)

    born_in = _born_in_statement()
    occurrence = occurrence_iri(
        unit_id=source.unit_id,
        statement=born_in,
    )

    assert (
        entity_iri("Ada Lovelace"),
        predicate_iri("bornIn"),
        entity_iri("London"),
    ) in graph

    assert (
        entity_iri("Ada Lovelace"),
        predicate_iri("birthYear"),
        Literal("1815", datatype=XSD.gYear, normalize=False),
    ) in graph

    assert (
        occurrence,
        RDF.type,
        GP.GroundedStatementOccurrence,
    ) in graph
    assert (
        occurrence,
        GP.provenanceToken,
        Literal(
            occurrence_token(
                unit_id=source.unit_id,
                statement=born_in,
            )
        ),
    ) in graph

    subject_spans = set(graph.objects(occurrence, GP.subjectEvidence))

    assert subject_spans == {
        span_iri(
            unit_id=source.unit_id,
            span=born_in.subject.evidence[0],
        ),
        span_iri(
            unit_id=source.unit_id,
            span=born_in.subject.evidence[1],
        ),
    }


def test_span_resources_preserve_exact_grounding_metadata() -> None:
    source = _source()
    statement = _born_in_statement()
    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(statement,),
    )

    dataset = build_extraction_dataset(source, extraction)
    graph = dataset.graph(unit_graph_iri(source.unit_id))

    london_span = statement.object.evidence[0]
    resource = span_iri(
        unit_id=source.unit_id,
        span=london_span,
    )

    assert (resource, RDF.type, GP.TextSpan) in graph
    assert (resource, GP.segment, Literal("text")) in graph
    assert (
        resource,
        GP.start,
        Literal(
            16,
            datatype=XSD.nonNegativeInteger,
            normalize=False,
        ),
    ) in graph
    assert (
        resource,
        GP.end,
        Literal(
            22,
            datatype=XSD.nonNegativeInteger,
            normalize=False,
        ),
    ) in graph
    assert (resource, GP.quote, Literal("London")) in graph


def test_trig_serialization_is_deterministic_and_parseable() -> None:
    source = _source()
    extraction = _extraction(source)

    first = serialize_extraction_trig(source, extraction)
    second = serialize_extraction_trig(source, extraction)

    assert first == second
    assert first.startswith(f"GRAPH <{unit_graph_iri(source.unit_id)}> {{")

    parsed = Dataset()
    parsed.parse(data=first, format="trig")

    graph = parsed.graph(unit_graph_iri(source.unit_id))

    assert (
        entity_iri("Ada Lovelace"),
        predicate_iri("bornIn"),
        entity_iri("London"),
    ) in graph
    assert len(parsed.default_graph) == 0


def test_exact_duplicate_occurrences_are_deduplicated() -> None:
    source = _source()
    statement = _born_in_statement()
    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(statement, statement),
    )

    dataset = build_extraction_dataset(source, extraction)
    graph = dataset.graph(unit_graph_iri(source.unit_id))

    occurrences = set(
        graph.subjects(
            RDF.type,
            GP.GroundedStatementOccurrence,
        )
    )

    assert occurrences == {
        occurrence_iri(
            unit_id=source.unit_id,
            statement=statement,
        )
    }


def test_same_semantic_triple_in_different_units_has_distinct_occurrences() -> None:
    first_source = _source(punctuation=".")
    second_source = _source(punctuation="!")
    statement = _born_in_statement()

    first_occurrence = occurrence_iri(
        unit_id=first_source.unit_id,
        statement=statement,
    )
    second_occurrence = occurrence_iri(
        unit_id=second_source.unit_id,
        statement=statement,
    )

    assert first_occurrence != second_occurrence
