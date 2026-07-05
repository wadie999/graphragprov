"""Parse untrusted model responses into validated grounded extractions."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from json import JSONDecodeError
from typing import Any, cast

from graphragprov.domain.source_unit import SourceUnit
from graphragprov.extraction.grounded_value import GroundedValue
from graphragprov.extraction.localization import localize_evidence
from graphragprov.extraction.result import ExtractionResult
from graphragprov.extraction.span import TextSegment, TextSpan
from graphragprov.extraction.statement import (
    GroundedStatement,
    LiteralDatatype,
)


def parse_extraction_response(
    source: SourceUnit,
    payload: str,
) -> ExtractionResult:
    """Convert one model-facing JSON response into a validated result."""

    try:
        raw_result = json.loads(payload)
    except JSONDecodeError as error:
        raise ValueError(
            f"invalid extraction JSON at line {error.lineno}, column {error.colno}: {error.msg}"
        ) from error

    result_data = _require_object(raw_result, "response")
    _validate_keys(
        result_data,
        required={"statements"},
        optional=set(),
        location="response",
    )

    raw_statements = result_data["statements"]

    if not isinstance(raw_statements, list):
        raise ValueError("response.statements must be a list")

    statements = tuple(
        _parse_statement(source, raw_statement, statement_index)
        for statement_index, raw_statement in enumerate(raw_statements)
    )

    result = ExtractionResult(
        unit_id=source.unit_id,
        statements=statements,
    )
    result.validate_against(source)

    return result


def _parse_statement(
    source: SourceUnit,
    raw_statement: Any,
    statement_index: int,
) -> GroundedStatement:
    location = f"response.statements[{statement_index}]"
    statement_data = _require_object(raw_statement, location)

    _validate_keys(
        statement_data,
        required={"subject", "predicate", "object"},
        optional=set(),
        location=location,
    )

    subject, subject_datatype = _parse_grounded_value(
        source,
        statement_data["subject"],
        location=f"{location}.subject",
        allow_datatype=False,
    )
    predicate, predicate_datatype = _parse_grounded_value(
        source,
        statement_data["predicate"],
        location=f"{location}.predicate",
        allow_datatype=False,
    )
    object_, object_datatype = _parse_grounded_value(
        source,
        statement_data["object"],
        location=f"{location}.object",
        allow_datatype=True,
    )

    if subject_datatype is not None or predicate_datatype is not None:
        raise AssertionError("subject and predicate datatypes are impossible")

    return GroundedStatement(
        subject=subject,
        predicate=predicate,
        object=object_,
        object_datatype=object_datatype,
    )


def _parse_grounded_value(
    source: SourceUnit,
    raw_value: Any,
    *,
    location: str,
    allow_datatype: bool,
) -> tuple[GroundedValue, LiteralDatatype | None]:
    value_data = _require_object(raw_value, location)

    optional_keys = {"datatype"} if allow_datatype else set()

    _validate_keys(
        value_data,
        required={"value", "evidence"},
        optional=optional_keys,
        location=location,
    )

    value = value_data["value"]

    if not isinstance(value, str):
        raise ValueError(f"{location}.value must be a string")

    if not value.strip():
        raise ValueError(f"{location}.value must not be empty")

    datatype = _parse_datatype(
        value_data.get("datatype"),
        value=value,
        location=location,
    )

    raw_evidence = value_data["evidence"]

    if not isinstance(raw_evidence, list):
        raise ValueError(f"{location}.evidence must be a list")

    if not raw_evidence:
        raise ValueError(f"{location}.evidence must not be empty")

    evidence = tuple(
        _parse_evidence(
            source,
            raw_item,
            location=f"{location}.evidence[{evidence_index}]",
        )
        for evidence_index, raw_item in enumerate(raw_evidence)
    )

    return GroundedValue(value=value, evidence=evidence), datatype


def _parse_evidence(
    source: SourceUnit,
    raw_evidence: Any,
    *,
    location: str,
) -> TextSpan:
    evidence_data = _require_object(raw_evidence, location)

    _validate_keys(
        evidence_data,
        required={"segment", "quote", "occurrence"},
        optional=set(),
        location=location,
    )

    raw_segment = evidence_data["segment"]

    if not isinstance(raw_segment, str):
        raise ValueError(f"{location}.segment must be a string")

    try:
        segment = TextSegment(raw_segment)
    except ValueError as error:
        raise ValueError(
            f"{location}.segment must be 'title' or 'text', received {raw_segment!r}"
        ) from error

    quote = evidence_data["quote"]

    if not isinstance(quote, str):
        raise ValueError(f"{location}.quote must be a string")

    occurrence = evidence_data["occurrence"]

    if type(occurrence) is not int:
        raise ValueError(f"{location}.occurrence must be an integer")

    try:
        return localize_evidence(
            source,
            segment=segment,
            quote=quote,
            occurrence=occurrence,
        )
    except ValueError as error:
        raise ValueError(f"{location}: {error}") from error


def _parse_datatype(
    raw_datatype: Any,
    *,
    value: str,
    location: str,
) -> LiteralDatatype | None:
    if raw_datatype is None:
        return None

    if not isinstance(raw_datatype, str):
        raise ValueError(f"{location}.datatype must be a string")

    try:
        datatype = LiteralDatatype(raw_datatype)
    except ValueError as error:
        allowed = ", ".join(item.value for item in LiteralDatatype)
        raise ValueError(f"{location}.datatype must be one of: {allowed}") from error

    _validate_literal_value(
        value,
        datatype=datatype,
        location=f"{location}.value",
    )

    return datatype


def _validate_literal_value(
    value: str,
    *,
    datatype: LiteralDatatype,
    location: str,
) -> None:
    if datatype is LiteralDatatype.STRING:
        return

    if datatype is LiteralDatatype.INTEGER:
        if re.fullmatch(r"(?:0|-[1-9]\d*|[1-9]\d*)", value) is None:
            raise ValueError(f"{location} must use canonical integer notation")
        return

    if datatype is LiteralDatatype.DECIMAL:
        if re.fullmatch(r"-?(?:0|[1-9]\d*)\.\d+", value) is None:
            raise ValueError(f"{location} must use canonical decimal notation")
        return

    if datatype is LiteralDatatype.BOOLEAN:
        if value not in {"true", "false"}:
            raise ValueError(f"{location} must be exactly 'true' or 'false'")
        return

    if datatype is LiteralDatatype.YEAR:
        if re.fullmatch(r"\d{4}", value) is None:
            raise ValueError(f"{location} must use YYYY notation")
        return

    if datatype is LiteralDatatype.YEAR_MONTH:
        if re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])", value) is None:
            raise ValueError(f"{location} must use YYYY-MM notation")
        return

    if datatype is LiteralDatatype.DATE:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
            raise ValueError(f"{location} must use YYYY-MM-DD notation")

        try:
            date.fromisoformat(value)
        except ValueError as error:
            raise ValueError(f"{location} is not a valid calendar date") from error

        return

    if datatype is LiteralDatatype.DATE_TIME:
        if "T" not in value:
            raise ValueError(f"{location} must use ISO 8601 date-time notation")

        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(f"{location} is not a valid ISO 8601 date-time") from error


def _require_object(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be a JSON object")

    return cast(dict[str, Any], value)


def _validate_keys(
    data: dict[str, Any],
    *,
    required: set[str],
    optional: set[str],
    location: str,
) -> None:
    keys = set(data)
    missing = required - keys
    unexpected = keys - required - optional

    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"{location} is missing required field(s): {missing_text}")

    if unexpected:
        unexpected_text = ", ".join(sorted(unexpected))
        raise ValueError(f"{location} contains unexpected field(s): {unexpected_text}")
