from rdflib import Literal
from rdflib.namespace import XSD

from graphragprov.domain.source_unit import SourceUnit
from graphragprov.extraction.grounded_value import GroundedValue
from graphragprov.extraction.result import ExtractionResult
from graphragprov.extraction.span import TextSegment, TextSpan
from graphragprov.extraction.statement import GroundedStatement, LiteralDatatype
from graphragprov.hashing import source_unit_id
from graphragprov.rdf.provenance import occurrence_token
from graphragprov.rdf.star import serialize_extraction_trig_star
from graphragprov.rdf.terms import rdf_triple, unit_graph_iri


def _source() -> SourceUnit:
    title = "Ada Lovelace"
    text = "She was born in London in 1815."

    return SourceUnit(unit_id=source_unit_id(title=title, text=text), title=title, text=text)


def _subject(*, include_pronoun: bool = True) -> GroundedValue:
    evidence = [TextSpan(segment=TextSegment.TITLE, start=0, end=12, quote="Ada Lovelace")]

    if include_pronoun:
        evidence.append(TextSpan(segment=TextSegment.TEXT, start=0, end=3, quote="She"))

    return GroundedValue(value="Ada Lovelace", evidence=tuple(evidence))


def _born_in_statement(*, include_pronoun: bool = True) -> GroundedStatement:
    return GroundedStatement(
        subject=_subject(include_pronoun=include_pronoun),
        predicate=GroundedValue(
            value="bornIn",
            evidence=(TextSpan(segment=TextSegment.TEXT, start=8, end=15, quote="born in"),),
        ),
        object=GroundedValue(
            value="London",
            evidence=(TextSpan(segment=TextSegment.TEXT, start=16, end=22, quote="London"),),
        ),
    )


def _birth_year_statement() -> GroundedStatement:
    return GroundedStatement(
        subject=_subject(),
        predicate=GroundedValue(
            value="birthYear",
            evidence=(TextSpan(segment=TextSegment.TEXT, start=8, end=12, quote="born"),),
        ),
        object=GroundedValue(
            value="1815",
            evidence=(TextSpan(segment=TextSegment.TEXT, start=26, end=30, quote="1815"),),
        ),
        object_datatype=LiteralDatatype.YEAR,
    )


def _triple_line(statement: GroundedStatement) -> str:
    subject, predicate, object_ = rdf_triple(statement)
    return f"{subject.n3()} {predicate.n3()} {object_.n3()} ."


def _annotation_line(*, source: SourceUnit, statement: GroundedStatement) -> str:
    subject, predicate, object_ = rdf_triple(statement)
    token = occurrence_token(unit_id=source.unit_id, statement=statement)

    return f'<< {subject.n3()} {predicate.n3()} {object_.n3()} >> textprov:occurrenceOf "{token}" .'


def test_serialization_contains_asserted_triple_and_annotation() -> None:
    source = _source()
    statement = _born_in_statement()
    extraction = ExtractionResult(unit_id=source.unit_id, statements=(statement,))

    output = serialize_extraction_trig_star(source, extraction)

    assert _triple_line(statement) in output
    assert _annotation_line(source=source, statement=statement) in output
    assert "@prefix textprov: <http://example.org/> ." in output
    assert output.startswith("@prefix textprov:")
    assert f"GRAPH {unit_graph_iri(source.unit_id).n3()} {{" in output


def test_serialization_is_deterministic() -> None:
    source = _source()
    extraction = ExtractionResult(
        unit_id=source.unit_id, statements=(_born_in_statement(), _birth_year_statement())
    )

    first = serialize_extraction_trig_star(source, extraction)
    second = serialize_extraction_trig_star(source, extraction)

    assert first == second


def test_same_triple_with_different_evidence_has_two_annotations() -> None:
    source = _source()
    title_and_pronoun = _born_in_statement(include_pronoun=True)
    title_only = _born_in_statement(include_pronoun=False)

    extraction = ExtractionResult(
        unit_id=source.unit_id, statements=(title_and_pronoun, title_only)
    )

    output = serialize_extraction_trig_star(source, extraction)

    assert output.count(_triple_line(title_and_pronoun)) == 1
    assert _annotation_line(source=source, statement=title_and_pronoun) in output
    assert _annotation_line(source=source, statement=title_only) in output
    assert output.count("<< ") == 2


def test_exact_duplicate_occurrences_are_deduplicated() -> None:
    source = _source()
    statement = _born_in_statement()

    extraction = ExtractionResult(unit_id=source.unit_id, statements=(statement, statement))

    output = serialize_extraction_trig_star(source, extraction)

    assert output.count(_triple_line(statement)) == 1
    assert output.count("<< ") == 1


def test_multiple_evidence_spans_are_preserved_in_token() -> None:
    source = _source()
    statement = _born_in_statement(include_pronoun=True)

    token = occurrence_token(unit_id=source.unit_id, statement=statement)

    assert ":s=tl:0-12+tx:0-3:" in token


def test_typed_literal_preserves_datatype() -> None:
    source = _source()
    statement = _birth_year_statement()

    extraction = ExtractionResult(unit_id=source.unit_id, statements=(statement,))

    output = serialize_extraction_trig_star(source, extraction)

    expected_literal = Literal("1815", datatype=XSD.gYear, normalize=False)

    assert expected_literal.n3() in output
    assert _triple_line(statement) in output
    assert _annotation_line(source=source, statement=statement) in output


def test_invalid_evidence_is_rejected_before_serialization() -> None:
    source = _source()

    invalid_statement = GroundedStatement(
        subject=GroundedValue(
            value="Ada Lovelace",
            evidence=(TextSpan(segment=TextSegment.TEXT, start=0, end=3, quote="Not She"),),
        ),
        predicate=GroundedValue(
            value="bornIn",
            evidence=(TextSpan(segment=TextSegment.TEXT, start=8, end=15, quote="born in"),),
        ),
        object=GroundedValue(
            value="London",
            evidence=(TextSpan(segment=TextSegment.TEXT, start=16, end=22, quote="London"),),
        ),
    )

    extraction = ExtractionResult(unit_id=source.unit_id, statements=(invalid_statement,))

    try:
        serialize_extraction_trig_star(source, extraction)
    except ValueError as error:
        assert "Not She" in str(error)
    else:
        raise AssertionError("invalid evidence was not rejected")
