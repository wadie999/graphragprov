"""Natural-language to SPARQL planning over one frozen graph snapshot."""

from __future__ import annotations

import os
from uuid import uuid4

from graphragprov.providers.deepseek import deepseek_generator
from graphragprov.qaagent import parse_qa_agent_response
from graphragprov.workbench_api.config import PlannerConfig
from graphragprov.workbench_api.models.execution import QueryPlan
from graphragprov.workbench_api.models.snapshot import CaseSnapshot
from graphragprov.workbench_api.services.planner_prompt import build_planner_prompt
from graphragprov.workbench_api.services.store import WorkbenchStore


class QueryPlanner:
    def __init__(self, config: PlannerConfig, store: WorkbenchStore) -> None:
        self._config = config
        self._store = store

    @property
    def available(self) -> bool:
        return bool(os.getenv(self._config.api_key_env, "").strip())

    def create(self, snapshot: CaseSnapshot, question: str) -> QueryPlan:
        if snapshot.graph is None:
            raise ValueError("selected snapshot has no frozen graph")
        api_key = os.getenv(self._config.api_key_env, "")
        if not api_key.strip():
            raise RuntimeError(
                f"missing planner API key environment variable {self._config.api_key_env}"
            )
        generate = deepseek_generator(
            api_key=api_key,
            model=self._config.model,
            max_tokens=self._config.max_tokens,
            timeout_seconds=self._config.timeout_seconds,
        )
        decision = parse_qa_agent_response(
            generate(build_planner_prompt(question, snapshot.graph.ntriples))
        )
        plan = QueryPlan(
            plan_id=f"p_{uuid4().hex}",
            snapshot_id=snapshot.snapshot_id,
            question=question.strip(),
            status=decision.status,
            sparql=decision.sparql,
            rationale=decision.rationale,
            assumptions=decision.assumptions,
            model=self._config.model,
        )
        self._store.write_plan(plan)
        return plan
