"""Project stored benchmark execution into the common QueryRun model."""

from graphragprov.workbench_api.artifacts import ArtifactCase
from graphragprov.workbench_api.models.graph import GraphSnapshot
from graphragprov.workbench_api.models.run import QueryRun, RunError
from graphragprov.workbench_api.services.provenance import (
    from_serialized_answers,
    stable_reference_id,
)


def project_reference_run(
    snapshot_id: str, artifact: ArtifactCase, graph: GraphSnapshot | None
) -> QueryRun | None:
    provenance = artifact.final_provenance
    if provenance is not None:
        return _from_provenance(snapshot_id, artifact, graph, provenance)
    if artifact.query_attempts:
        return _from_query_attempt(snapshot_id, artifact, artifact.query_attempts[-1])
    return None


def _from_provenance(
    snapshot_id: str,
    artifact: ArtifactCase,
    graph: GraphSnapshot | None,
    provenance: dict[str, object],
) -> QueryRun:
    execution = provenance.get("execution")
    execution = execution if isinstance(execution, dict) else {}
    error = _error(provenance)
    return QueryRun(
        run_id=stable_reference_id(snapshot_id),
        snapshot_id=snapshot_id,
        origin="reference",
        question=artifact.question,
        semantic_sparql=str(provenance.get("semantic_sparql", "")),
        execution_sparql=_string(provenance.get("scoped_sparql")),
        rewritten_sparql=_string(execution.get("rewritten_query")),
        result=_dict_or_none(execution.get("original_result")),
        rewritten_result=_dict_or_none(execution.get("rewritten_result")),
        provenance_status=str(provenance.get("provenance_status", "not_requested")),
        provenance=from_serialized_answers(provenance.get("answer_provenances"), graph),
        answer_correct=_last_bool(artifact, "answer_correct"),
        gold_support_covered=_last_bool(artifact, "gold_support_covered"),
        provenance_error=error,
    )


def _from_query_attempt(
    snapshot_id: str, artifact: ArtifactCase, attempt: dict[str, object]
) -> QueryRun:
    plan = attempt.get("plan")
    plan = plan if isinstance(plan, dict) else {}
    error_message = attempt.get("validation_error")
    return QueryRun(
        run_id=stable_reference_id(snapshot_id),
        snapshot_id=snapshot_id,
        origin="reference",
        question=artifact.question,
        semantic_sparql=str(plan.get("semantic_sparql", plan.get("sparql", ""))),
        execution_sparql=_string(attempt.get("execution_sparql")),
        rewritten_sparql=None,
        result=_dict_or_none(attempt.get("original_result")),
        rewritten_result=None,
        provenance_status="failed" if error_message else "not_requested",
        provenance=(),
        answer_correct=_bool(attempt.get("answer_correct")),
        gold_support_covered=_bool(attempt.get("gold_support_covered")),
        error=(
            RunError(error_type="ReferenceExecutionError", message=str(error_message))
            if error_message
            else None
        ),
    )


def _error(data: dict[str, object]) -> RunError | None:
    message = data.get("error_message")
    if not isinstance(message, str) or not message:
        return None
    return RunError(error_type=str(data.get("error_type", "ProvenanceError")), message=message)


def _last_bool(artifact: ArtifactCase, key: str) -> bool | None:
    if not artifact.query_attempts:
        return None
    return _bool(artifact.query_attempts[-1].get(key))


def _bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _dict_or_none(value: object) -> dict[str, object] | None:
    return dict(value) if isinstance(value, dict) else None
