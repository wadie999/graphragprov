"""Resolution of NPCS provenance into exact source evidence."""

from __future__ import annotations

from dataclasses import dataclass

from graphragprov.domain import SourceUnit
from graphragprov.extraction import TextSpan
from graphragprov.provenance.polynomial import parse_provenance_polynomial
from graphragprov.provenance.registry import SourceRegistry
from graphragprov.rdf.provenance import EvidenceLocation, decode_occurrence_token


@dataclass(frozen=True, slots=True)
class DecodedProvenanceOccurrence:
    """Exact source evidence represented by one provenance token.

    The semantic RDF triple is not reconstructed here. It remains available
    from the RDF-star statement carrying the token. The compact statement hash
    is retained so the occurrence can later be checked against that triple.
    """

    token: str
    compact_unit_id: str
    source: SourceUnit
    subject_evidence: tuple[TextSpan, ...]
    predicate_evidence: tuple[TextSpan, ...]
    object_evidence: tuple[TextSpan, ...]
    triple_hash: str

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable representation."""

        return {
            "token": self.token,
            "compact_unit_id": self.compact_unit_id,
            "source": {
                "unit_id": self.source.unit_id,
                "title": self.source.title,
                "text": self.source.text,
            },
            "subject_evidence": [_span_to_dict(span) for span in self.subject_evidence],
            "predicate_evidence": [_span_to_dict(span) for span in self.predicate_evidence],
            "object_evidence": [_span_to_dict(span) for span in self.object_evidence],
            "triple_hash": self.triple_hash,
        }


@dataclass(frozen=True, slots=True)
class DecodedProvenanceDerivation:
    """One complete conjunctive derivation of a query answer."""

    occurrences: tuple[DecodedProvenanceOccurrence, ...]

    def __post_init__(self) -> None:
        if not self.occurrences:
            raise ValueError("decoded provenance derivation must contain at least one occurrence")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable representation."""

        return {"occurrences": [occurrence.to_dict() for occurrence in self.occurrences]}


@dataclass(frozen=True, slots=True)
class DecodedProvenance:
    """Exact source evidence for all alternative query derivations."""

    derivations: tuple[DecodedProvenanceDerivation, ...]

    def __post_init__(self) -> None:
        if not self.derivations:
            raise ValueError("decoded provenance must contain at least one derivation")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable representation."""

        return {"derivations": [derivation.to_dict() for derivation in self.derivations]}


def decode_provenance_polynomial(value: str, *, registry: SourceRegistry) -> DecodedProvenance:
    """Decode an NPCS polynomial into exact validated source spans."""

    polynomial = parse_provenance_polynomial(value)

    return DecodedProvenance(
        derivations=tuple(
            DecodedProvenanceDerivation(
                occurrences=tuple(
                    _decode_occurrence(token, registry=registry) for token in derivation
                )
            )
            for derivation in polynomial.derivations
        )
    )


def _decode_occurrence(token: str, *, registry: SourceRegistry) -> DecodedProvenanceOccurrence:
    decoded = decode_occurrence_token(token)

    try:
        source = registry.resolve(decoded.compact_unit_id)
    except KeyError as error:
        raise ValueError(
            f"cannot decode provenance token with unknown source unit {decoded.compact_unit_id}"
        ) from error

    return DecodedProvenanceOccurrence(
        token=token,
        compact_unit_id=decoded.compact_unit_id,
        source=source,
        subject_evidence=_resolve_evidence(
            source=source, token=token, role="subject", locations=decoded.subject_evidence
        ),
        predicate_evidence=_resolve_evidence(
            source=source, token=token, role="predicate", locations=decoded.predicate_evidence
        ),
        object_evidence=_resolve_evidence(
            source=source, token=token, role="object", locations=decoded.object_evidence
        ),
        triple_hash=decoded.triple_hash,
    )


def _resolve_evidence(
    *, source: SourceUnit, token: str, role: str, locations: tuple[EvidenceLocation, ...]
) -> tuple[TextSpan, ...]:
    return tuple(
        _resolve_location(source=source, token=token, role=role, location=location)
        for location in locations
    )


def _resolve_location(
    *, source: SourceUnit, token: str, role: str, location: EvidenceLocation
) -> TextSpan:
    segment_text = source.title if location.segment.value == "title" else source.text

    span = TextSpan(
        segment=location.segment,
        start=location.start,
        end=location.end,
        quote=segment_text[location.start : location.end],
    )

    try:
        span.validate_against(source)
    except ValueError as error:
        raise ValueError(
            f"invalid {role} evidence in provenance token {token!r}: {error}"
        ) from error

    return span


def _span_to_dict(span: TextSpan) -> dict[str, object]:
    return {
        "segment": span.segment.value,
        "start": span.start,
        "end": span.end,
        "quote": span.quote,
    }
