from graphragprov.domain.source_unit import SourceUnit
from graphragprov.extraction.grounded_value import GroundedValue
from graphragprov.extraction.result import ExtractionResult
from graphragprov.extraction.span import TextSegment, TextSpan
from graphragprov.extraction.statement import GroundedStatement
from graphragprov.hashing import source_unit_id
from graphragprov.rdf.provenance import occurrence_token
from graphragprov.rdf.star import serialize_extraction_trig_star
from graphragprov.rdf.terms import rdf_triple, unit_graph_iri
from graphragprov.rdf.vocabulary import GP


def _source() -> SourceUnit:
    title = "Ada Lovelace"
    text = "She was born in London."

    return SourceUnit(
        unit_id=source_unit_id(title=title, text=text),
        title=title,
        text=text,
    )


def _statement(
    *,
    include_pronoun_evidence: bool = True,
) -> GroundedStatement:
    subject_evidence = [
        TextSpan(
            segment=TextSegment.TITLE,
            start=0,
            end=12,
            quote="Ada Lovelace",
        )
    ]

    if include_pronoun_evidence:
        subject_evidence.append(
            TextSpan(
                segment=TextSegment.TEXT,
                start=0,
                end=3,
                quote="She",
            )
        )

    return GroundedStatement(
        subject=GroundedValue(
            value="Ada Lovelace",
            evidence=tuple(subject_evidence),
        ),
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


def _annotation_line(
    *,
    source: SourceUnit,
    statement: GroundedStatement,
) -> str:
    subject, predicate, object_ = rdf_triple(statement)
    token = occurrence_token(
        unit_id=source.unit_id,
        statement=statement,
    )

    return (
        f'<< {subject.n3()} {predicate.n3()} {object_.n3()} >> {GP.occurrenceOf.n3()} "{token}" .'
    )


def test_trig_star_serialization_is_deterministic() -> None:
    source = _source()
    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(_statement(),),
    )

    first = serialize_extraction_trig_star(source, extraction)
    second = serialize_extraction_trig_star(source, extraction)

    assert first == second
    assert first.startswith(f"GRAPH {unit_graph_iri(source.unit_id).n3()} {{")
    assert (
        _annotation_line(
            source=source,
            statement=extraction.statements[0],
        )
        in first
    )


def test_same_triple_with_different_evidence_has_two_annotations() -> None:
    source = _source()
    title_and_pronoun = _statement(include_pronoun_evidence=True)
    title_only = _statement(include_pronoun_evidence=False)

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            title_and_pronoun,
            title_only,
        ),
    )

    output = serialize_extraction_trig_star(source, extraction)

    assert (
        _annotation_line(
            source=source,
            statement=title_and_pronoun,
        )
        in output
    )
    assert (
        _annotation_line(
            source=source,
            statement=title_only,
        )
        in output
    )
    assert output.count("<< ") == 2


def test_exact_duplicate_occurrences_have_one_annotation() -> None:
    source = _source()
    statement = _statement()

    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(
            statement,
            statement,
        ),
    )

    output = serialize_extraction_trig_star(source, extraction)

    assert output.count("<< ") == 1


def test_trig_star_keeps_standard_occurrence_metadata() -> None:
    source = _source()
    extraction = ExtractionResult(
        unit_id=source.unit_id,
        statements=(_statement(),),
    )

    output = serialize_extraction_trig_star(source, extraction)

    assert GP.GroundedStatementOccurrence.n3() in output
    assert GP.provenanceToken.n3() in output
    assert GP.subjectEvidence.n3() in output
    assert GP.predicateEvidence.n3() in output
    assert GP.objectEvidence.n3() in output
