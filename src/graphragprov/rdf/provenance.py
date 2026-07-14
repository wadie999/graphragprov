"""Deterministic provenance tokens for grounded RDF statements."""

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
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

_CODE_SEGMENT: dict[str, TextSegment] = {code: segment for segment, code in _SEGMENT_CODE.items()}

_SEGMENT_ORDER: dict[TextSegment, int] = {
    TextSegment.TITLE: 0,
    TextSegment.TEXT: 1,
}

_SPAN_PATTERN = r"(?:tl|tx):[0-9]+-[0-9]+"
_EVIDENCE_PATTERN = rf"{_SPAN_PATTERN}(?:\+{_SPAN_PATTERN})*"

_TOKEN_PATTERN = re.compile(
    rf"(?P<unit_id>u_[0-9a-f]{{{UNIT_ID_HEX_LENGTH}}})"
    rf":s=(?P<subject>{_EVIDENCE_PATTERN})"
    rf":p=(?P<predicate>{_EVIDENCE_PATTERN})"
    rf":o=(?P<object>{_EVIDENCE_PATTERN})"
    rf":t=(?P<triple_hash>[0-9a-f]{{{TRIPLE_HASH_HEX_LENGTH}}})"
)

_SPAN_LOCATION_PATTERN = re.compile(
    r"(?P<segment>tl|tx):"
    r"(?P<start>[0-9]+)-"
    r"(?P<end>[0-9]+)"
)

SpanLocation = tuple[TextSegment, int, int]


@dataclass(frozen=True, slots=True)
class EvidenceLocation:
    """One exact title or text location encoded in a provenance token."""

    segment: TextSegment
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError("evidence start must be non-negative")

        if self.end <= self.start:
            raise ValueError("evidence end must be greater than start")


@dataclass(frozen=True, slots=True)
class DecodedOccurrenceToken:
    """Structured representation of one grounded occurrence token."""

    compact_unit_id: str
    subject_evidence: tuple[EvidenceLocation, ...]
    predicate_evidence: tuple[EvidenceLocation, ...]
    object_evidence: tuple[EvidenceLocation, ...]
    triple_hash: str


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


def decode_occurrence_token(token: str) -> DecodedOccurrenceToken:
    """Parse and validate one grounded occurrence token."""

    match = _TOKEN_PATTERN.fullmatch(token)

    if match is None:
        raise ValueError("invalid grounded occurrence token")

    return DecodedOccurrenceToken(
        compact_unit_id=match.group("unit_id"),
        subject_evidence=_decode_evidence(match.group("subject")),
        predicate_evidence=_decode_evidence(match.group("predicate")),
        object_evidence=_decode_evidence(match.group("object")),
        triple_hash=match.group("triple_hash"),
    )


def validate_occurrence_token(token: str) -> None:
    """Reject a malformed grounded-statement token."""

    decode_occurrence_token(token)


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
        location = (
            span.segment,
            span.start,
            span.end,
        )
        existing = spans_by_location.get(location)

        if existing is not None and existing.quote != span.quote:
            raise ValueError(
                "evidence contains conflicting quotes for "
                f"{span.segment.value} span "
                f"[{span.start}:{span.end}]"
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


def _decode_evidence(
    value: str,
) -> tuple[EvidenceLocation, ...]:
    locations = tuple(_decode_span_location(part) for part in value.split("+"))

    canonical_locations = tuple(
        sorted(
            set(locations),
            key=lambda location: (
                _SEGMENT_ORDER[location.segment],
                location.start,
                location.end,
            ),
        )
    )

    if locations != canonical_locations:
        raise ValueError("evidence locations must be unique and canonically ordered")

    return locations


def _decode_span_location(
    value: str,
) -> EvidenceLocation:
    match = _SPAN_LOCATION_PATTERN.fullmatch(value)

    if match is None:
        raise ValueError(f"invalid evidence location: {value}")

    return EvidenceLocation(
        segment=_CODE_SEGMENT[match.group("segment")],
        start=int(match.group("start")),
        end=int(match.group("end")),
    )


def _evidence_token(
    evidence: Iterable[TextSpan],
) -> str:
    return "+".join(span_location_token(span) for span in canonical_evidence(evidence))


def _evidence_locations(
    evidence: Iterable[TextSpan],
) -> list[str]:
    return [span_location_token(span) for span in canonical_evidence(evidence)]


def _statement_payload(
    statement: GroundedStatement,
) -> dict[str, object]:
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
