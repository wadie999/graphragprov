"""Interactive SPARQL execution against one immutable case snapshot."""

from uuid import uuid4

from graphragprov.qaagent import compile_scoped_select_query
from graphragprov.workbench_api.artifacts import ArtifactCase
from graphragprov.workbench_api.models.execution import QueryRunRequest
from graphragprov.workbench_api.models.graph import GraphSnapshot
from graphragprov.workbench_api.models.run import QueryRun, RunError
from graphragprov.workbench_api.ports import ProvenanceRewriter, SnapshotWorkspace
from graphragprov.workbench_api.services.live_provenance import execute_provenance
from graphragprov.workbench_api.services.query_results import bindings
from graphragprov.workbench_api.services.store import WorkbenchStore


class QueryExecutor:
    def __init__(
        self, workspace: SnapshotWorkspace, npcs: ProvenanceRewriter, store: WorkbenchStore
    ) -> None:
        self._workspace, self._npcs, self._store = workspace, npcs, store

    def run(
        self,
        *,
        snapshot_id: str,
        artifact: ArtifactCase,
        graph: GraphSnapshot,
        request: QueryRunRequest,
    ) -> QueryRun:
        semantic = request.sparql.strip()
        scoped = compile_scoped_select_query(semantic, source_unit_ids=artifact.support_source_ids)
        with self._workspace.materialized(artifact) as graphdb:
            try:
                result = graphdb.query(scoped)
            except Exception as error:
                return self._save(_failed(snapshot_id, request, semantic, scoped, error))
            run = _base_run(snapshot_id, request, semantic, scoped, result)
            if not bindings(result):
                return self._save(run.model_copy(update={"provenance_status": "no_answers"}))
            try:
                live = execute_provenance(
                    semantic_sparql=scoped,
                    artifact=artifact,
                    graph=graph,
                    graphdb=graphdb,
                    npcs=self._npcs,
                )
                run = run.model_copy(
                    update={
                        "rewritten_sparql": live.rewritten_sparql,
                        "rewritten_result": live.rewritten_result,
                        "provenance_status": "decoded",
                        "provenance": live.answers,
                    }
                )
            except Exception as error:
                run = run.model_copy(
                    update={"provenance_status": "failed", "provenance_error": _error(error)}
                )
        return self._save(run)

    def _save(self, run: QueryRun) -> QueryRun:
        self._store.write_run(run)
        return run


def _base_run(
    snapshot_id: str,
    request: QueryRunRequest,
    semantic: str,
    scoped: str,
    result: dict[str, object],
) -> QueryRun:
    return QueryRun(
        run_id=f"r_{uuid4().hex}",
        snapshot_id=snapshot_id,
        origin=request.origin,
        question=request.question,
        semantic_sparql=semantic,
        execution_sparql=scoped,
        rewritten_sparql=None,
        result=result,
        rewritten_result=None,
        provenance_status="not_requested",
        provenance=(),
    )


def _failed(
    snapshot_id: str, request: QueryRunRequest, semantic: str, scoped: str, error: Exception
) -> QueryRun:
    return _base_run(snapshot_id, request, semantic, scoped, {}).model_copy(
        update={"result": None, "error": _error(error)}
    )


def _error(error: Exception) -> RunError:
    return RunError(error_type=type(error).__name__, message=str(error))
