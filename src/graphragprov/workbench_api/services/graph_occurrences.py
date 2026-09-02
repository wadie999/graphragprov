"""Project exact grounded statement occurrences from experiment artifacts."""

from typing import Literal

from graphragprov.extraction import TextSpan
from graphragprov.rdf.provenance import occurrence_token
from graphragprov.rdf.terms import rdf_triple
from graphragprov.workbench_api.artifacts import ArtifactCase
from graphragprov.workbench_api.models.graph import StatementOccurrence
from graphragprov.workbench_api.models.source import EvidenceSpan
from graphragprov.workbench_api.services.graph_terms import signature, stable_id

OccurrenceProjection = tuple[tuple[str, ...], StatementOccurrence]
EvidenceRole = Literal["subject", "predicate", "object"]


def project_occurrences(artifact: ArtifactCase) -> list[OccurrenceProjection]:
    result: list[OccurrenceProjection] = []

    for run in artifact.extraction_runs:
        for statement in run.extraction.statements:
            subject, predicate, object_value = rdf_triple(statement)
            triple_signature = signature(subject, predicate, object_value)
            token = occurrence_token(unit_id=run.source.unit_id, statement=statement)

            result.append(
                (
                    triple_signature,
                    StatementOccurrence(
                        occurrence_id=stable_id("o", token),
                        token=token,
                        semantic_edge_id=stable_id("e", "\0".join(triple_signature)),
                        source_id=run.source.unit_id,
                        subject_evidence=_spans(statement.subject.evidence, "subject"),
                        predicate_evidence=_spans(statement.predicate.evidence, "predicate"),
                        object_evidence=_spans(statement.object.evidence, "object"),
                    ),
                )
            )

    return result


def _spans(spans: tuple[TextSpan, ...], role: EvidenceRole) -> tuple[EvidenceSpan, ...]:
    return tuple(
        EvidenceSpan(
            segment=span.segment.value, start=span.start, end=span.end, quote=span.quote, role=role
        )
        for span in spans
    )
