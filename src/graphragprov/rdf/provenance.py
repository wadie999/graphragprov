"""Deterministic provenance tokens for grounded RDF statements."""

import json
import re
from collections.abc import Iterable
from hashlib import sha256

from graphragprov.extraction.span import TextSegment, TextSpan
from graphragprov.extraction.statement import GroundedStatement
from graphragprov.hashing import validate_source_unit_id

UNIT_ID_HEX_LENGTH = 16
TRIPLE_HASH_HEX_LENGTH = 8
STATEMENT_FORMAT_VERSION = "statement-v1"

_SEGMENT_CODE: dict[TextSegment, str] = {
    TextSegment.TITLE: "tl",
    TextSegment.TEXT: "tx",
}

_SEGMENT_ORDER: dict[TextSegment, int] = {
    TextSegment.TITLE: 0,
    TextSegment.TEXT: 1,
}

_SPAN_PATTERN = r"(?:tl|tx):[0-9]+-[0-9]+"
_EVIDENCE_PATTERN = rf"{_SPAN_PATTERN}(?:\+{_SPAN_PATTERN})*"

_TOKEN_PATTERN = re.compile(
    rf"u_[0-9a-f]{{{UNIT_ID_HEX_LENGTH}}}"
    rf":s={_EVIDENCE_PATTERN}"
    rf":p={_EVIDENCE_PATTERN}"
    rf":o={_EVIDENCE_PATTERN}"
    rf":t=[0-9a-f]{{{TRIPLE_HASH_HEX_LENGTH}}}"
)

SpanLocation = tuple[TextSegment, int, int]


def compact_unit_id(unit_id: str) -> str:
    """Return the compact source-unit identifier used in provenance tokens."""

    validate_source_unit_id(unit_id)

    digest = unit_id.removeprefix("u_")
    return f"u_{digest[:UNIT_ID_HEX_LENGTH]}"


def occurrence_token(
    *,
    unit_id: str,
    statement: GroundedStatement,
) -> str:
    """Return the compact NPCS token of one grounded statement occurrence."""

    return (
        f"{compact_unit_id(unit_id)}"
        f":s={_evidence_token(statement.subject.evidence)}"
        f":p={_evidence_token(statement.predicate.evidence)}"
        f":o={_evidence_token(statement.object.evidence)}"
        f":t={statement_digest(statement)[:TRIPLE_HASH_HEX_LENGTH]}"
    )


def validate_occurrence_token(token: str) -> None:
    """Reject a malformed grounded-statement token."""

    if _TOKEN_PATTERN.fullmatch(token) is None:
        raise ValueError("invalid grounded occurrence token")


def statement_digest(statement: GroundedStatement) -> str:
    """Return the SHA-256 digest of the semantic RDF-like statement."""

    return sha256(canonical_statement_bytes(statement)).hexdigest()


def canonical_statement_bytes(statement: GroundedStatement) -> bytes:
    """Serialize the semantic statement deterministically."""

    return _canonical_json_bytes(_statement_payload(statement))


def canonical_occurrence_bytes(
    *,
    unit_id: str,
    statement: GroundedStatement,
) -> bytes:
    """Serialize the complete occurrence for collision verification."""

    validate_source_unit_id(unit_id)

    payload = {
        "unit_id": unit_id,
        "statement": _statement_payload(statement),
        "subject_evidence": _evidence_locations(statement.subject.evidence),
        "predicate_evidence": _evidence_locations(statement.predicate.evidence),
        "object_evidence": _evidence_locations(statement.object.evidence),
    }

    return _canonical_json_bytes(payload)


def canonical_evidence(
    evidence: Iterable[TextSpan],
) -> tuple[TextSpan, ...]:
    """Deduplicate and deterministically order evidence spans."""

    spans_by_location: dict[SpanLocation, TextSpan] = {}

    for span in evidence:
        location = (span.segment, span.start, span.end)
        existing = spans_by_location.get(location)

        if existing is not None and existing.quote != span.quote:
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
    """Encode one title or text span."""

    segment = _SEGMENT_CODE[span.segment]
    return f"{segment}:{span.start}-{span.end}"


def _evidence_token(evidence: Iterable[TextSpan]) -> str:
    return "+".join(
        span_location_token(span)
        for span in canonical_evidence(evidence)
    )


def _evidence_locations(evidence: Iterable[TextSpan]) -> list[str]:
    return [
        span_location_token(span)
        for span in canonical_evidence(evidence)
    ]


def _statement_payload(statement: GroundedStatement) -> dict[str, object]:
    if statement.object_datatype is None:
        object_payload: dict[str, str] = {
            "kind": "entity",
            "value": statement.object.value,
        }
    else:
        object_payload = {
            "kind": "literal",
            "value": statement.object.value,
            "datatype": statement.object_datatype.value,
        }

    return {
        "version": STATEMENT_FORMAT_VERSION,
        "subject": statement.subject.value,
        "predicate": statement.predicate.value,
        "object": object_payload,
    }


def _canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")