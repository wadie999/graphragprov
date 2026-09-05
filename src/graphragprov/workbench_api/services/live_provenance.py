"""Execute rewritten SPARQL and resolve its provenance to source evidence."""

from dataclasses import dataclass

from graphragprov.npcs import QueryRewriter
from graphragprov.provenance import SourceRegistry, decode_provenance_polynomial
from graphragprov.workbench_api.artifacts import ArtifactCase
from graphragprov.workbench_api.models.execution import ProvenanceAnswer
from graphragprov.workbench_api.models.graph import GraphSnapshot
from graphragprov.workbench_api.ports import GraphQueryBackend
from graphragprov.workbench_api.services.provenance import from_decoded_answers
from graphragprov.workbench_api.services.query_results import bindings


@dataclass(frozen=True, slots=True)
class DecodedAnswer:
    binding: dict[str, object]
    polynomial: str
    decoded: object


@dataclass(frozen=True, slots=True)
class LiveProvenance:
    rewritten_sparql: str
    rewritten_result: dict[str, object]
    answers: tuple[ProvenanceAnswer, ...]


def execute_provenance(
    *,
    semantic_sparql: str,
    artifact: ArtifactCase,
    graph: GraphSnapshot,
    graphdb: GraphQueryBackend,
    npcs: QueryRewriter,
) -> LiveProvenance:
    rewrite = npcs.rewrite_detailed(semantic_sparql)
    rewritten_result = graphdb.query(rewrite.sparql)

    decoded = _decode(
        rewritten_result,
        artifact,
        rewrite.provenance_variable,
    )

    return LiveProvenance(
        rewritten_sparql=rewrite.sparql,
        rewritten_result=rewritten_result,
        answers=from_decoded_answers(decoded, graph),
    )


def _decode(
    rewritten_result: dict[str, object],
    artifact: ArtifactCase,
    provenance_variable: str,
) -> tuple[DecodedAnswer, ...]:
    registry = SourceRegistry(run.source for run in artifact.extraction_runs)
    answers: list[DecodedAnswer] = []

    for binding in bindings(rewritten_result):
        provenance = binding.get(provenance_variable)

        if not isinstance(provenance, dict):
            raise ValueError(
                f"rewritten binding has no {provenance_variable!r}"
            )

        polynomial = provenance.get("value")

        if not isinstance(polynomial, str) or not polynomial.strip():
            raise ValueError(
                "provenance polynomial must be a non-empty string"
            )

        semantic = {
            key: value
            for key, value in binding.items()
            if key != provenance_variable
        }

        decoded = decode_provenance_polynomial(
            polynomial,
            registry=registry,
        )

        answers.append(DecodedAnswer(semantic, polynomial, decoded))

    return tuple(answers)