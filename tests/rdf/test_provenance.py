import pytest

from graphragprov.extraction.grounded_value import GroundedValue
from graphragprov.extraction.span import TextSegment, TextSpan
from graphragprov.extraction.statement import GroundedStatement, LiteralDatatype
from graphragprov.hashing import source_unit_id
from graphragprov.rdf.provenance import occurrence_token


def _ada_statement(
    *,
    predicate_value: str = "bornIn",
    subject_evidence: tuple[TextSpan, ...] | None = None,
    object_value: str = "London",
    object_evidence: tuple[TextSpan, ...] | None = None,
    object_datatype: LiteralDatatype | None = None,
) -> GroundedStatement:
    if subject_evidence is None:
        subject_evidence = (
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
        )

    if object_evidence is None:
        object_evidence = (
            TextSpan(
                segment=TextSegment.TEXT,
                start=16,
                end=22,
                quote="London",
            ),
        )

    return GroundedStatement(
        subject=GroundedValue(
            value="Ada Lovelace",
            evidence=subject_evidence,
        ),
        predicate=GroundedValue(
            value=predicate_value,
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
            value=object_value,
            evidence=object_evidence,
        ),
        object_datatype=object_datatype,
    )


def test_different_semantic_statements_with_same_evidence_have_different_tokens() -> None:
    unit_id = source_unit_id(
        title="Ada Lovelace",
        text="She was born in London in 1815.",
    )

    born_in = _ada_statement(predicate_value="bornIn")
    birthplace = _ada_statement(predicate_value="hasBirthplace")

    assert occurrence_token(
        unit_id=unit_id,
        statement=born_in,
    ) != occurrence_token(
        unit_id=unit_id,
        statement=birthplace,
    )


def test_same_statement_with_different_evidence_has_different_tokens() -> None:
    unit_id = source_unit_id(
        title="Ada Lovelace",
        text="She was born in London in 1815.",
    )

    title_span = TextSpan(
        segment=TextSegment.TITLE,
        start=0,
        end=12,
        quote="Ada Lovelace",
    )
    pronoun_span = TextSpan(
        segment=TextSegment.TEXT,
        start=0,
        end=3,
        quote="She",
    )

    title_only = _ada_statement(subject_evidence=(title_span,))
    title_and_pronoun = _ada_statement(
        subject_evidence=(title_span, pronoun_span),
    )

    assert occurrence_token(
        unit_id=unit_id,
        statement=title_only,
    ) != occurrence_token(
        unit_id=unit_id,
        statement=title_and_pronoun,
    )


def test_same_statement_in_different_source_units_has_different_tokens() -> None:
    first_unit_id = source_unit_id(
        title="Ada Lovelace",
        text="She was born in London in 1815.",
    )
    second_unit_id = source_unit_id(
        title="Ada Lovelace",
        text="She was born in London in 1815!",
    )
    statement = _ada_statement()

    assert occurrence_token(
        unit_id=first_unit_id,
        statement=statement,
    ) != occurrence_token(
        unit_id=second_unit_id,
        statement=statement,
    )


def test_literal_datatype_contributes_to_statement_identity() -> None:
    unit_id = source_unit_id(
        title="Ada Lovelace",
        text="She was born in London in 1815.",
    )
    year_evidence = (
        TextSpan(
            segment=TextSegment.TEXT,
            start=26,
            end=30,
            quote="1815",
        ),
    )

    year_statement = _ada_statement(
        object_value="1815",
        object_evidence=year_evidence,
        object_datatype=LiteralDatatype.YEAR,
    )
    integer_statement = _ada_statement(
        object_value="1815",
        object_evidence=year_evidence,
        object_datatype=LiteralDatatype.INTEGER,
    )

    assert occurrence_token(
        unit_id=unit_id,
        statement=year_statement,
    ) != occurrence_token(
        unit_id=unit_id,
        statement=integer_statement,
    )


def test_conflicting_quotes_for_same_span_are_rejected() -> None:
    unit_id = source_unit_id(
        title="Ada Lovelace",
        text="She was born in London in 1815.",
    )
    statement = _ada_statement(
        subject_evidence=(
            TextSpan(
                segment=TextSegment.TITLE,
                start=0,
                end=12,
                quote="Ada Lovelace",
            ),
            TextSpan(
                segment=TextSegment.TITLE,
                start=0,
                end=12,
                quote="Different text",
            ),
        ),
    )

    with pytest.raises(ValueError, match="conflicting quotes"):
        occurrence_token(unit_id=unit_id, statement=statement)


def test_noncanonical_source_unit_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="full 64-character"):
        occurrence_token(
            unit_id="u_0a5e4e80",
            statement=_ada_statement(),
        )


def test_occurrence_token_is_deterministic_and_canonicalizes_evidence() -> None:
    unit_id = source_unit_id(
        title="Ada Lovelace",
        text="She was born in London in 1815.",
    )

    title_span = TextSpan(
        segment=TextSegment.TITLE,
        start=0,
        end=12,
        quote="Ada Lovelace",
    )
    pronoun_span = TextSpan(
        segment=TextSegment.TEXT,
        start=0,
        end=3,
        quote="She",
    )

    ordered_statement = _ada_statement(
        subject_evidence=(title_span, pronoun_span),
    )
    reordered_statement = _ada_statement(
        subject_evidence=(pronoun_span, title_span, title_span),
    )

    expected = "u_aaa084a0b97f0658:s=tl:0-12+tx:0-3:p=tx:8-15:o=tx:16-22:t=5e4dedbc"

    assert occurrence_token(unit_id=unit_id, statement=ordered_statement) == expected
    assert occurrence_token(unit_id=unit_id, statement=reordered_statement) == expected
