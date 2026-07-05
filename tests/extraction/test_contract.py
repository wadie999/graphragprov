import pytest

from graphragprov.domain import SourceUnit
from graphragprov.extraction import (
    ExtractionResult,
    GroundedStatement,
    GroundedValue,
    LiteralDatatype,
    TextSegment,
    TextSpan,
)
from graphragprov.hashing import source_unit_id

TITLE = "Albert Einstein"
TEXT = "He was born in Ulm."

SOURCE = SourceUnit(
    unit_id=source_unit_id(title=TITLE, text=TEXT),
    title=TITLE,
    text=TEXT,
)


def valid_result() -> ExtractionResult:
    return ExtractionResult(
        unit_id=SOURCE.unit_id,
        statements=(
            GroundedStatement(
                subject=GroundedValue(
                    value="Albert Einstein",
                    evidence=(
                        TextSpan(
                            segment=TextSegment.TITLE,
                            start=0,
                            end=15,
                            quote="Albert Einstein",
                        ),
                        TextSpan(
                            segment=TextSegment.TEXT,
                            start=0,
                            end=2,
                            quote="He",
                        ),
                    ),
                ),
                predicate=GroundedValue(
                    value="born in",
                    evidence=(
                        TextSpan(
                            segment=TextSegment.TEXT,
                            start=7,
                            end=14,
                            quote="born in",
                        ),
                    ),
                ),
                object=GroundedValue(
                    value="Ulm",
                    evidence=(
                        TextSpan(
                            segment=TextSegment.TEXT,
                            start=15,
                            end=18,
                            quote="Ulm",
                        ),
                    ),
                ),
            ),
        ),
    )


def test_valid_grounded_result() -> None:
    valid_result().validate_against(SOURCE)


def test_title_and_text_can_both_ground_a_value() -> None:
    subject = valid_result().statements[0].subject

    assert subject.evidence[0].segment is TextSegment.TITLE
    assert subject.evidence[1].segment is TextSegment.TEXT


def test_mismatching_quote_is_rejected() -> None:
    result = ExtractionResult(
        unit_id=SOURCE.unit_id,
        statements=(
            GroundedStatement(
                subject=GroundedValue(
                    value="Albert Einstein",
                    evidence=(
                        TextSpan(
                            segment=TextSegment.TITLE,
                            start=0,
                            end=15,
                            quote="Someone Else",
                        ),
                    ),
                ),
                predicate=valid_result().statements[0].predicate,
                object=valid_result().statements[0].object,
            ),
        ),
    )

    with pytest.raises(ValueError, match="expected"):
        result.validate_against(SOURCE)


def test_out_of_bounds_span_is_rejected() -> None:
    span = TextSpan(
        segment=TextSegment.TEXT,
        start=15,
        end=200,
        quote="Ulm",
    )

    with pytest.raises(ValueError, match="exceeds"):
        span.validate_against(SOURCE)


def test_wrong_unit_id_is_rejected() -> None:
    result = ExtractionResult(
        unit_id="u_wrong",
        statements=valid_result().statements,
    )

    with pytest.raises(ValueError, match="does not match"):
        result.validate_against(SOURCE)


def test_grounded_value_requires_evidence() -> None:
    with pytest.raises(ValueError, match="evidence"):
        GroundedValue(
            value="Albert Einstein",
            evidence=(),
        )


def test_json_round_trip() -> None:
    result = valid_result()

    restored = ExtractionResult.from_json(result.to_json())

    assert restored == result
    restored.validate_against(SOURCE)


def test_entity_object_has_no_datatype() -> None:
    statement = valid_result().statements[0]

    assert statement.object_datatype is None
    assert not statement.object_is_literal
    assert "datatype" not in statement.to_dict()["object"]


def test_literal_object_preserves_datatype() -> None:
    original = valid_result().statements[0]

    statement = GroundedStatement(
        subject=original.subject,
        predicate=original.predicate,
        object=original.object,
        object_datatype=LiteralDatatype.STRING,
    )

    assert statement.object_is_literal
    assert statement.to_dict()["object"]["datatype"] == "string"

    restored = GroundedStatement.from_dict(statement.to_dict())

    assert restored == statement


def test_unknown_literal_datatype_is_rejected() -> None:
    data = valid_result().statements[0].to_dict()
    data["object"]["datatype"] = "unknown"

    with pytest.raises(ValueError):
        GroundedStatement.from_dict(data)
