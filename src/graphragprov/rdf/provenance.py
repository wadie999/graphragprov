"""Deterministic identities for grounded statement occurrences."""

import json
import re
from collections.abc import Iterable
from hashlib import sha256

from graphragprov.extraction.span import TextSegment, TextSpan
from graphragprov.extraction.statement import GroundedStatement
from graphragprov.hashing import validate_source_unit_id

TOKEN_VERSION = "po1"
STATEMENT_FORMAT_VERSION = "statement-v1"
OCCURRENCE_FORMAT_VERSION = "occurrence-v1"

_SEGMENT_CODE: dict[TextSegment, str] = {
    TextSegment.TITLE: "tl",
    TextSegment.TEXT: "tx",
}

_SEGMENT_ORDER: dict[TextSegment, int] = {
    TextSegment.TITLE: 0,
    TextSegment.TEXT: 1,
}

_TOKEN_PATTERN = re.compile(r"po1:u_[0-9a-f]{64}:.+")

SpanLocation = tuple[TextSegment, int, int]


def canonical_statement_bytes(statement: GroundedStatement) -> bytes:
    """Serialize one semantic statement deterministically."""

    return _canonical_json_bytes(_statement_payload(statement))


def canonical_occurrence_bytes(
    *,
    unit_id: str,
    statement: GroundedStatement,
) -> bytes:
    """Serialize the complete grounded occurrence deterministically."""

    validate_source_unit_id(unit_id)

    payload = {
        "object_evidence": [
            span_location_token(span) for span in canonical_evidence(statement.object.evidence)
        ],
        "occurrence_version": OCCURRENCE_FORMAT_VERSION,
        "predicate_evidence": [
            span_location_token(span) for span in canonical_evidence(statement.predicate.evidence)
        ],
        "statement": _statement_payload(statement),
        "subject_evidence": [
            span_location_token(span) for span in canonical_evidence(statement.subject.evidence)
        ],
        "unit_id": unit_id,
    }

    return _canonical_json_bytes(payload)


def statement_digest(statement: GroundedStatement) -> str:
    """Return the full SHA-256 digest of a canonical semantic statement."""

    return sha256(canonical_statement_bytes(statement)).hexdigest()


def occurrence_token(
    *,
    unit_id: str,
    statement: GroundedStatement,
) -> str:
    """Return the deterministic token of one grounded statement occurrence.

    The statement evidence must already have been validated against the
    corresponding immutable SourceUnit.
    """

    validate_source_unit_id(unit_id)

    subject_evidence = _encode_evidence(statement.subject.evidence)
    predicate_evidence = _encode_evidence(statement.predicate.evidence)
    object_evidence = _encode_evidence(statement.object.evidence)

    return (
        f"{TOKEN_VERSION}:{unit_id}"
        f":s={subject_evidence}"
        f":p={predicate_evidence}"
        f":o={object_evidence}"
        f":t={statement_digest(statement)}"
    )


def validate_occurrence_token(token: str) -> None:
    """Reject malformed or abbreviated occurrence tokens."""

    if _TOKEN_PATTERN.fullmatch(token) is None:
        raise ValueError("invalid grounded occurrence token")


def canonical_evidence(
    evidence: Iterable[TextSpan],
) -> tuple[TextSpan, ...]:
    """Deduplicate and deterministically order evidence spans."""

    spans_by_location: dict[SpanLocation, TextSpan] = {}

    for span in evidence:
        location = (span.segment, span.start, span.end)
        existing_span = spans_by_location.get(location)

        if existing_span is not None and existing_span.quote != span.quote:
            raise ValueError(
                "evidence contains conflicting quotes for "
                f"{span.segment.value} span [{span.start}:{span.end}]"
            )

        spans_by_location[location] = span

    if not spans_by_location:
        raise ValueError("evidence must contain at least one span")

    return tuple(
        sorted(
            spans_by_location.values(),
            key=lambda span: (
                _SEGMENT_ORDER[span.segment],
                span.start,
                span.end,
            ),
        )
    )


def span_location_token(span: TextSpan) -> str:
    """Encode the location of one source span."""

    return f"{_SEGMENT_CODE[span.segment]}:{span.start}-{span.end}"


def _statement_payload(statement: GroundedStatement) -> dict[str, object]:
    if statement.object_datatype is None:
        object_data: dict[str, str] = {
            "kind": "entity",
            "value": statement.object.value,
        }
    else:
        object_data = {
            "datatype": statement.object_datatype.value,
            "kind": "literal",
            "value": statement.object.value,
        }

    return {
        "object": object_data,
        "predicate": statement.predicate.value,
        "subject": statement.subject.value,
        "version": STATEMENT_FORMAT_VERSION,
    }


def _encode_evidence(evidence: Iterable[TextSpan]) -> str:
    return "+".join(span_location_token(span) for span in canonical_evidence(evidence))


def _canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
