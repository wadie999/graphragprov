"""NPCS execution and decoding for one already-executed semantic query."""

from dataclasses import dataclass

from graphragprov.provenance import SourceRegistry, decode_provenance_polynomial
from graphragprov.query import PROVENANCE_VARIABLE
from graphragprov.workbench_api.artifacts import ArtifactCase
from graphragprov.workbench_api.models.execution import ProvenanceAnswer
from graphragprov.workbench_api.models.graph import GraphSnapshot
from graphragprov.workbench_api.ports import GraphQueryBackend, ProvenanceRewriter
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
    npcs: ProvenanceRewriter,
) -> LiveProvenance:
    rewritten = npcs.rewrite(semantic_sparql)
    rewritten_result = graphdb.query(rewritten)
    decoded = _decode(rewritten_result, artifact)
    return LiveProvenance(
        rewritten_sparql=rewritten,
        rewritten_result=rewritten_result,
        answers=from_decoded_answers(decoded, graph),
    )


def _decode(
    rewritten_result: dict[str, object], artifact: ArtifactCase
) -> tuple[DecodedAnswer, ...]:
    registry = SourceRegistry(run.source for run in artifact.extraction_runs)
    answers: list[DecodedAnswer] = []
    for binding in bindings(rewritten_result):
        provenance = binding.get(PROVENANCE_VARIABLE)
        if not isinstance(provenance, dict) or not isinstance(provenance.get("value"), str):
            raise ValueError(f"rewritten binding has no {PROVENANCE_VARIABLE!r}")
        polynomial = provenance["value"]
        semantic = {key: value for key, value in binding.items() if key != PROVENANCE_VARIABLE}
        decoded = decode_provenance_polynomial(polynomial, registry=registry)
        answers.append(DecodedAnswer(semantic, polynomial, decoded))
    return tuple(answers)
