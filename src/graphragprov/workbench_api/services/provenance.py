"""Convert decoded provenance records into stable API resources."""

from __future__ import annotations

from hashlib import sha256

from graphragprov.workbench_api.models.execution import (
    ProvenanceAnswer,
    ProvenanceDerivation,
    ProvenanceFactor,
)
from graphragprov.workbench_api.models.graph import GraphSnapshot


def from_serialized_answers(
    answers: object, graph: GraphSnapshot | None
) -> tuple[ProvenanceAnswer, ...]:
    if not isinstance(answers, list):
        return ()
    occurrence_ids = _token_index(graph)
    result: list[ProvenanceAnswer] = []
    for answer in answers:
        if not isinstance(answer, dict):
            continue
        decoded = answer.get("decoded")
        derivations = decoded.get("derivations") if isinstance(decoded, dict) else None
        result.append(
            ProvenanceAnswer(
                binding=_dict(answer.get("binding")),
                polynomial=str(answer.get("polynomial", "")),
                derivations=_serialized_derivations(derivations, occurrence_ids),
            )
        )
    return tuple(result)


def from_decoded_answers(
    answers: tuple[object, ...], graph: GraphSnapshot | None
) -> tuple[ProvenanceAnswer, ...]:
    occurrence_ids = _token_index(graph)
    result: list[ProvenanceAnswer] = []
    for answer in answers:
        binding = getattr(answer, "binding", {})
        polynomial = str(getattr(answer, "polynomial", ""))
        decoded = getattr(answer, "decoded", None)
        derivations = getattr(decoded, "derivations", ())
        projected: list[ProvenanceDerivation] = []
        for index, derivation in enumerate(derivations, start=1):
            factors = tuple(
                ProvenanceFactor(token=item.token, occurrence_id=occurrence_ids.get(item.token))
                for item in derivation.occurrences
            )
            projected.append(ProvenanceDerivation(derivation_id=f"d{index}", factors=factors))
        result.append(
            ProvenanceAnswer(
                binding=dict(binding), polynomial=polynomial, derivations=tuple(projected)
            )
        )
    return tuple(result)


def _serialized_derivations(
    value: object, occurrence_ids: dict[str, str]
) -> tuple[ProvenanceDerivation, ...]:
    if not isinstance(value, list):
        return ()
    result: list[ProvenanceDerivation] = []
    for index, derivation in enumerate(value, start=1):
        occurrences = derivation.get("occurrences") if isinstance(derivation, dict) else None
        if not isinstance(occurrences, list):
            continue
        factors = tuple(
            ProvenanceFactor(
                token=str(item.get("token", "")),
                occurrence_id=occurrence_ids.get(str(item.get("token", ""))),
            )
            for item in occurrences
            if isinstance(item, dict)
        )
        result.append(ProvenanceDerivation(derivation_id=f"d{index}", factors=factors))
    return tuple(result)


def _token_index(graph: GraphSnapshot | None) -> dict[str, str]:
    if graph is None:
        return {}
    return {item.token: item.occurrence_id for item in graph.occurrences}


def stable_reference_id(snapshot_id: str) -> str:
    digest = sha256(f"reference\0{snapshot_id}".encode()).hexdigest()[:20]
    return f"r_{digest}"


def _dict(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}
