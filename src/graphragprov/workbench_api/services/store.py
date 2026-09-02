"""Filesystem persistence for interactive workbench objects."""

from __future__ import annotations

import json
from pathlib import Path

from graphragprov.workbench_api.models.execution import QueryPlan
from graphragprov.workbench_api.models.run import QueryRun


class WorkbenchStore:
    def __init__(self, root: Path) -> None:
        self._plans = root / "query-plans"
        self._runs = root / "query-runs"
        self._plans.mkdir(parents=True, exist_ok=True)
        self._runs.mkdir(parents=True, exist_ok=True)

    def write_plan(self, plan: QueryPlan) -> None:
        self._write(self._plans / f"{plan.plan_id}.json", plan.model_dump(mode="json"))

    def plan(self, plan_id: str) -> QueryPlan:
        return QueryPlan.model_validate_json((self._plans / f"{plan_id}.json").read_text())

    def write_run(self, run: QueryRun) -> None:
        self._write(self._runs / f"{run.run_id}.json", run.model_dump(mode="json"))

    def run(self, run_id: str) -> QueryRun:
        return QueryRun.model_validate_json((self._runs / f"{run_id}.json").read_text())

    def runs_for(self, snapshot_id: str) -> tuple[QueryRun, ...]:
        items: list[QueryRun] = []
        for path in sorted(self._runs.glob("*.json"), key=lambda item: item.stat().st_mtime):
            run = QueryRun.model_validate_json(path.read_text(encoding="utf-8"))
            if run.snapshot_id == snapshot_id:
                items.append(run)
        return tuple(items)

    @staticmethod
    def _write(path: Path, data: dict[str, object]) -> None:
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(path)
