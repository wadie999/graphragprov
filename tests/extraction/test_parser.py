import json

import pytest

from graphragprov.domain import SourceUnit
from graphragprov.extraction import (
    LiteralDatatype,
    TextSegment,
    parse_extraction_response,
)

SOURCE = SourceUnit(
    unit_id="u_system_owned",
    title="Albert Einstein",
    text=("He was born in Ulm on 14 March 1879. Einstein later visited Ulm."),
)


def valid_response() -> dict[str, object]:
    return {
        "statements": [
            {
                "subject": {
                    "value": "Albert Einstein",
                    "evidence": [
                        {
                            "segment": "title",
                            "quote": "Albert Einstein",
                            "occurrence": 1,
                        },
                        {
                            "segment": "text",
                            "quote": "He",
                            "occurrence": 1,
                        },
                    ],
                },
                "predicate": {
                    "value": "bornIn",
                    "evidence": [
                        {
                            "segment": "text",
                            "quote": "born in",
                            "occurrence": 1,
                        }
                    ],
                },
                "object": {
                    "value": "Ulm",
                    "evidence": [
                        {
                            "segment": "text",
                            "quote": "Ulm",
                            "occurrence": 1,
                        }
                    ],
                },
            },
            {
                "subject": {
                    "value": "Albert Einstein",
                    "evidence": [
                        {
                            "segment": "title",
                            "quote": "Albert Einstein",
                            "occurrence": 1,
                        },
                        {
                            "segment": "text",
                            "quote": "He",
                            "occurrence": 1,
                        },
                    ],
                },
                "predicate": {
                    "value": "birthDate",
                    "evidence": [
                        {
                            "segment": "text",
                            "quote": "born",
                            "occurrence": 1,
                        }
                    ],
                },
                "object": {
                    "value": "1879-03-14",
                    "datatype": "date",
                    "evidence": [
                        {
                            "segment": "text",
                            "quote": "14 March 1879",
                            "occurrence": 1,
                        }
                    ],
                },
            },
        ]
    }


def test_parses_valid_fake_model_response() -> None:
    result = parse_extraction_response(
        SOURCE,
        json.dumps(valid_response()),
    )

    assert result.unit_id == SOURCE.unit_id
    assert len(result.statements) == 2

    entity_statement = result.statements[0]
    literal_statement = result.statements[1]

    assert entity_statement.object.value == "Ulm"
    assert entity_statement.object_datatype is None
    assert not entity_statement.object_is_literal

    assert literal_statement.object.value == "1879-03-14"
    assert literal_statement.object_datatype is LiteralDatatype.DATE
    assert literal_statement.object_is_literal


def test_localizes_title_and_text_evidence_independently() -> None:
    result = parse_extraction_response(
        SOURCE,
        json.dumps(valid_response()),
    )

    evidence = result.statements[0].subject.evidence

    assert evidence[0].segment is TextSegment.TITLE
    assert evidence[0].start == 0

    assert evidence[1].segment is TextSegment.TEXT
    assert evidence[1].start == 0


def test_localizes_repeated_quote_occurrence() -> None:
    response = valid_response()
    statements = response["statements"]
    assert isinstance(statements, list)

    statement = statements[0]
    assert isinstance(statement, dict)

    object_data = statement["object"]
    assert isinstance(object_data, dict)

    evidence = object_data["evidence"]
    assert isinstance(evidence, list)

    evidence[0]["occurrence"] = 2

    result = parse_extraction_response(
        SOURCE,
        json.dumps(response),
    )

    span = result.statements[0].object.evidence[0]

    assert span.start == SOURCE.text.rfind("Ulm")
    assert span.quote == "Ulm"


def test_accepts_empty_statement_list() -> None:
    result = parse_extraction_response(
        SOURCE,
        '{"statements": []}',
    )

    assert result.unit_id == SOURCE.unit_id
    assert result.statements == ()


def test_rejects_malformed_json() -> None:
    with pytest.raises(ValueError, match="invalid extraction JSON"):
        parse_extraction_response(
            SOURCE,
            '{"statements": [}',
        )


def test_rejects_model_supplied_unit_id() -> None:
    response = valid_response()
    response["unit_id"] = "u_model_supplied"

    with pytest.raises(ValueError, match="unexpected field.*unit_id"):
        parse_extraction_response(
            SOURCE,
            json.dumps(response),
        )


def test_rejects_model_supplied_offsets() -> None:
    response = valid_response()
    statements = response["statements"]
    assert isinstance(statements, list)

    statement = statements[0]
    assert isinstance(statement, dict)

    subject = statement["subject"]
    assert isinstance(subject, dict)

    evidence = subject["evidence"]
    assert isinstance(evidence, list)

    evidence[0]["start"] = 0
    evidence[0]["end"] = 15

    with pytest.raises(ValueError, match="unexpected field"):
        parse_extraction_response(
            SOURCE,
            json.dumps(response),
        )


def test_rejects_missing_evidence() -> None:
    response = valid_response()
    statements = response["statements"]
    assert isinstance(statements, list)

    statement = statements[0]
    assert isinstance(statement, dict)

    subject = statement["subject"]
    assert isinstance(subject, dict)

    subject["evidence"] = []

    with pytest.raises(ValueError, match="evidence must not be empty"):
        parse_extraction_response(
            SOURCE,
            json.dumps(response),
        )


def test_rejects_invalid_segment() -> None:
    response = valid_response()
    statements = response["statements"]
    assert isinstance(statements, list)

    statement = statements[0]
    assert isinstance(statement, dict)

    subject = statement["subject"]
    assert isinstance(subject, dict)

    evidence = subject["evidence"]
    assert isinstance(evidence, list)

    evidence[0]["segment"] = "paragraph"

    with pytest.raises(ValueError, match="must be 'title' or 'text'"):
        parse_extraction_response(
            SOURCE,
            json.dumps(response),
        )


def test_rejects_missing_occurrence() -> None:
    response = valid_response()
    statements = response["statements"]
    assert isinstance(statements, list)

    statement = statements[0]
    assert isinstance(statement, dict)

    object_data = statement["object"]
    assert isinstance(object_data, dict)

    evidence = object_data["evidence"]
    assert isinstance(evidence, list)

    del evidence[0]["occurrence"]

    with pytest.raises(ValueError, match="missing required field.*occurrence"):
        parse_extraction_response(
            SOURCE,
            json.dumps(response),
        )


def test_rejects_occurrence_out_of_range() -> None:
    response = valid_response()
    statements = response["statements"]
    assert isinstance(statements, list)

    statement = statements[0]
    assert isinstance(statement, dict)

    object_data = statement["object"]
    assert isinstance(object_data, dict)

    evidence = object_data["evidence"]
    assert isinstance(evidence, list)

    evidence[0]["occurrence"] = 3

    with pytest.raises(ValueError, match="occurrence 3 does not exist"):
        parse_extraction_response(
            SOURCE,
            json.dumps(response),
        )


def test_rejects_unknown_datatype() -> None:
    response = valid_response()
    statements = response["statements"]
    assert isinstance(statements, list)

    statement = statements[1]
    assert isinstance(statement, dict)

    object_data = statement["object"]
    assert isinstance(object_data, dict)

    object_data["datatype"] = "timestamp"

    with pytest.raises(ValueError, match="datatype must be one of"):
        parse_extraction_response(
            SOURCE,
            json.dumps(response),
        )


def test_rejects_invalid_normalized_date() -> None:
    response = valid_response()
    statements = response["statements"]
    assert isinstance(statements, list)

    statement = statements[1]
    assert isinstance(statement, dict)

    object_data = statement["object"]
    assert isinstance(object_data, dict)

    object_data["value"] = "1879-13-40"

    with pytest.raises(ValueError, match="not a valid calendar date"):
        parse_extraction_response(
            SOURCE,
            json.dumps(response),
        )
