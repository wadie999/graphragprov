"""Interactive SPARQL execution against one immutable case snapshot."""

from __future__ import annotations

import os
from uuid import uuid4

from graphragprov.npcs import NPCSClient
from graphragprov.provenance import SourceRegistry
from graphragprov.providers.deepseek import deepseek_generator
from graphragprov.qaagent import (
    QAAgentConfiguration,
    compile_scoped_select_query,
    run_tuple_qa_agent,
)
from graphragprov.qaagent.trace import QAQueryAttempt
from graphragprov.workbench_api.artifacts import ArtifactCase
from graphragprov.workbench_api.config import PlannerConfig
from graphragprov.workbench_api.models.execution import InteractiveQueryRequest, QueryRunRequest
from graphragprov.workbench_api.models.graph import GraphSnapshot
from graphragprov.workbench_api.models.run import QueryAttemptView, QueryRun, RunError
from graphragprov.workbench_api.services.live_provenance import execute_provenance
from graphragprov.workbench_api.services.provenance import from_decoded_answers
from graphragprov.workbench_api.services.query_results import bindings
from graphragprov.workbench_api.services.store import WorkbenchStore
from graphragprov.workbench_api.services.workspace import GraphWorkspaceManager


class QueryExecutor:
    def __init__(
        self,
        workspace: GraphWorkspaceManager,
        npcs: NPCSClient,
        store: WorkbenchStore,
        planner_config: PlannerConfig,
    ) -> None:
        self._workspace = workspace
        self._npcs = npcs
        self._store = store
        self._planner_config = planner_config

    def run(
        self,
        *,
        snapshot_id: str,
        artifact: ArtifactCase,
        graph: GraphSnapshot,
        request: QueryRunRequest,
    ) -> QueryRun:
        semantic = request.sparql.strip()

        scoped = compile_scoped_select_query(
            semantic,
            source_unit_ids=artifact.support_source_ids,
        )

        with self._workspace.materialized(artifact) as graphdb:
            try:
                result = graphdb.query(scoped)
            except Exception as error:
                return self._save(
                    _failed(
                        snapshot_id,
                        request,
                        semantic,
                        scoped,
                        error,
                    )
                )

            run = _base_run(
                snapshot_id,
                request,
                semantic,
                scoped,
                result,
            )

            if not bindings(result):
                return self._save(
                    run.model_copy(
                        update={
                            "provenance_status": "no_answers",
                        }
                    )
                )

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
                    update={
                        "provenance_status": "failed",
                        "provenance_error": _error(error),
                    }
                )

        return self._save(run)

    def run_interactive(
        self,
        *,
        snapshot_id: str,
        artifact: ArtifactCase,
        graph: GraphSnapshot,
        request: InteractiveQueryRequest,
    ) -> QueryRun:
        api_key = os.getenv(
            self._planner_config.api_key_env,
            "",
        )

        if not api_key.strip():
            raise RuntimeError(
                "missing planner API key environment variable "
                f"{self._planner_config.api_key_env}"
            )

        generate = deepseek_generator(
            api_key=api_key,
            model=self._planner_config.model,
            max_tokens=self._planner_config.max_tokens,
            timeout_seconds=self._planner_config.timeout_seconds,
        )

        configuration = QAAgentConfiguration(
            context_mode="graph_agent",
            graph_scope="case_all",
            answer_visibility="hidden",
            decomposition_visibility="none",
            max_turns=request.max_turns,
        )

        registry = SourceRegistry(
            run.source
            for run in artifact.extraction_runs
        )

        with self._workspace.materialized(artifact) as graphdb:
            result = run_tuple_qa_agent(
                question=request.question.strip(),
                hop_count=max(1, artifact.hop_count),
                configuration=configuration,
                query_source_unit_ids=artifact.support_source_ids,
                prompt_source_unit_ids=None,
                graphdb=graphdb,
                npcs=self._npcs,
                registry=registry,
                generate_response=generate,
            )

        attempts = tuple(
            _attempt_view(attempt)
            for attempt in result.query_attempts
        )

        if not result.query_attempts:
            run = QueryRun(
                run_id=f"r_{uuid4().hex}",
                snapshot_id=snapshot_id,
                origin="interactive",
                question=request.question.strip(),
                semantic_sparql="",
                execution_sparql=None,
                rewritten_sparql=None,
                result=None,
                rewritten_result=None,
                provenance_status=result.termination_reason,
                provenance=(),
                attempts=attempts,
                error=RunError(
                    error_type="AgentDecision",
                    message=result.decision.rationale,
                ),
            )

            return self._save(run)

        final = result.query_attempts[-1]
        execution = final.execution

        run = QueryRun(
            run_id=f"r_{uuid4().hex}",
            snapshot_id=snapshot_id,
            origin="interactive",
            question=request.question.strip(),
            semantic_sparql=final.semantic_sparql,
            execution_sparql=final.scoped_sparql,
            rewritten_sparql=(
                execution.rewritten_query
                if execution is not None
                else None
            ),
            result=(
                execution.original_result
                if execution is not None
                else None
            ),
            rewritten_result=(
                execution.rewritten_result
                if execution is not None
                else None
            ),
            provenance_status=final.provenance_status,
            provenance=from_decoded_answers(
                tuple(final.answer_provenances),
                graph,
            ),
            attempts=attempts,
            error=(
                RunError(
                    error_type=(
                        final.error_type
                        or "QueryAttemptError"
                    ),
                    message=final.error_message,
                )
                if final.error_message is not None
                else None
            ),
        )

        return self._save(run)

    def _save(
        self,
        run: QueryRun,
    ) -> QueryRun:
        self._store.write_run(run)
        return run


def _attempt_view(
    attempt: QAQueryAttempt,
) -> QueryAttemptView:
    execution = attempt.execution

    error = (
        RunError(
            error_type=(
                attempt.error_type
                or "QueryAttemptError"
            ),
            message=attempt.error_message,
        )
        if attempt.error_message is not None
        else None
    )

    return QueryAttemptView(
        turn_index=attempt.turn_index,
        purpose=attempt.purpose,
        semantic_sparql=attempt.semantic_sparql,
        execution_sparql=attempt.scoped_sparql,
        result=(
            execution.original_result
            if execution is not None
            else None
        ),
        rewritten_sparql=(
            execution.rewritten_query
            if execution is not None
            else None
        ),
        rewritten_result=(
            execution.rewritten_result
            if execution is not None
            else None
        ),
        provenance_status=attempt.provenance_status,
        error=error,
    )


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
    snapshot_id: str,
    request: QueryRunRequest,
    semantic: str,
    scoped: str,
    error: Exception,
) -> QueryRun:
    return _base_run(
        snapshot_id,
        request,
        semantic,
        scoped,
        {},
    ).model_copy(
        update={
            "result": None,
            "error": _error(error),
        }
    )


def _error(
    error: Exception,
) -> RunError:
    return RunError(
        error_type=type(error).__name__,
        message=str(error),
    )