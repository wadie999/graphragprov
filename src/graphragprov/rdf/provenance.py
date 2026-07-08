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

_UNIT_ID_PATTERN = re.compile(r"u_[0-9a-f]{64}")

_SEGMENT_CODE: dict[TextSegment, str] = {
    TextSegment.TITLE: "tl",
    TextSegment.TEXT: "tx",
}

_SEGMENT_ORDER: dict[TextSegment, int] = {
    TextSegment.TITLE: 0,
    TextSegment.TEXT: 1,
}

SpanLocation = tuple[TextSegment, int, int]


def canonical_statement_bytes(statement: GroundedStatement) -> bytes:
    """Serialize the semantic statement deterministically.

    The representation is independent from any RDF serialization library.
    It distinguishes entity objects from literal objects and preserves the
    normalized lexical form and datatype of literals.
    """

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

    payload = {
        "object": object_data,
        "predicate": statement.predicate.value,
        "subject": statement.subject.value,
        "version": STATEMENT_FORMAT_VERSION,
    }

    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def statement_digest(statement: GroundedStatement) -> str:
    """Return the full SHA-256 digest of a canonical semantic statement."""

    return sha256(canonical_statement_bytes(statement)).hexdigest()


def occurrence_token(
    *,
    unit_id: str,
    statement: GroundedStatement,
) -> str:
    """Return the deterministic token of one grounded statement occurrence.

    The caller must first validate the statement evidence against the
    corresponding immutable SourceUnit.

    Quotes are not repeated in the token because the source-unit identifier
    commits to the exact title and text, while segment and offsets uniquely
    recover each quote.
    """

    validate_source_unit_id(unit_id)

    subject_evidence = _encode_evidence(statement.subject.evidence)
    predicate_evidence = _encode_evidence(statement.predicate.evidence)
    object_evidence = _encode_evidence(statement.object.evidence)
    triple_digest = statement_digest(statement)

    return (
        f"{TOKEN_VERSION}:{unit_id}"
        f":s={subject_evidence}"
        f":p={predicate_evidence}"
        f":o={object_evidence}"
        f":t={triple_digest}"
    )


def _validate_unit_id(unit_id: str) -> None:
    if _UNIT_ID_PATTERN.fullmatch(unit_id) is None:
        raise ValueError(
            "unit ID must contain 'u_' followed by the full 64-character lowercase SHA-256 digest"
        )


def _encode_evidence(evidence: Iterable[TextSpan]) -> str:
    locations = _canonical_span_locations(evidence)

    return "+".join(f"{_SEGMENT_CODE[segment]}:{start}-{end}" for segment, start, end in locations)


def _canonical_span_locations(
    evidence: Iterable[TextSpan],
) -> tuple[SpanLocation, ...]:
    quotes_by_location: dict[SpanLocation, str] = {}

    for span in evidence:
        location = (span.segment, span.start, span.end)
        existing_quote = quotes_by_location.get(location)

        if existing_quote is not None and existing_quote != span.quote:
            raise ValueError(
                "evidence contains conflicting quotes for "
                f"{span.segment.value} span [{span.start}:{span.end}]"
            )

        quotes_by_location[location] = span.quote

    if not quotes_by_location:
        raise ValueError("evidence must contain at least one span")

    return tuple(
        sorted(
            quotes_by_location,
            key=lambda location: (
                _SEGMENT_ORDER[location[0]],
                location[1],
                location[2],
            ),
        )
    )
