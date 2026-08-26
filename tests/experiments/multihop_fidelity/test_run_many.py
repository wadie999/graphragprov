import argparse
import json
import sys
from pathlib import Path
from typing import cast

from pytest import MonkeyPatch

import graphragprov.experiments.multihop_fidelity.run_many as run_many_module
from graphragprov.experiments.multihop_fidelity.run_many import Job, _command, run_batch


def _arguments(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        query_scope="support",
        dataset_path=tmp_path / "dataset.json",
        artifacts=tmp_path / "runs",
        model="deepseek-test",
        max_tokens=4096,
        max_source_attempts=3,
        max_query_attempts=4,
        llm_timeout_seconds=60.0,
        resume=False,
        workers=2,
    )


def test_command_uses_supplied_worker_module(tmp_path: Path) -> None:
    arguments = _arguments(tmp_path)
    job = Job(1, "case-a", frozenset({"source-a"}))
    worker_module = "graphragprov.experiments.multihop_fidelity.run_one_twowiki"

    command = _command(arguments, job, True, worker_module=worker_module)

    assert command[:4] == [sys.executable, "-u", "-m", worker_module]
    assert command[command.index("--case-id") + 1] == "case-a"
    assert command[command.index("--query-scope") + 1] == "support"
    assert "--reuse-llm-checkpoints" in command


def test_run_batch_passes_worker_module_and_records_it(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    arguments = _arguments(tmp_path)
    jobs = (Job(1, "case-a", frozenset({"source-a"})),)
    worker_module = "graphragprov.experiments.multihop_fidelity.run_one_twowiki"
    called = False

    async def fake_run_parallel(
        args: argparse.Namespace, received_jobs: tuple[Job, ...], logs: Path, *, worker_module: str
    ) -> list[dict[str, object]]:
        nonlocal called

        called = True

        assert args is arguments
        assert received_jobs == jobs
        assert logs == arguments.artifacts / "_batch" / "logs"
        assert worker_module == ("graphragprov.experiments.multihop_fidelity.run_one_twowiki")

        return [{"index": 1, "case_id": "case-a", "status": "completed"}]

    monkeypatch.setattr(run_many_module, "_run_parallel", fake_run_parallel)

    exit_code = run_batch(args=arguments, jobs=jobs, worker_module=worker_module)

    assert exit_code == 0
    assert called is True

    summary = cast(
        dict[str, object],
        json.loads((arguments.artifacts / "_batch" / "summary.json").read_text(encoding="utf-8")),
    )

    assert summary["worker_module"] == worker_module
    assert summary["query_scope"] == "support"


def test_resume_skips_complete_result_but_retries_operational_failure(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    arguments = _arguments(tmp_path)
    arguments.resume = True

    jobs = (
        Job(1, "complete-case", frozenset({"source-a"})),
        Job(2, "failed-case", frozenset({"source-b"})),
    )

    complete_result = arguments.artifacts / "complete-case" / "support" / "result.json"
    failed_result = arguments.artifacts / "failed-case" / "support" / "result.json"

    complete_result.parent.mkdir(parents=True, exist_ok=True)
    failed_result.parent.mkdir(parents=True, exist_ok=True)

    complete_result.write_text(json.dumps({"outcome": {"status": "complete"}}), encoding="utf-8")

    failed_result.write_text(
        json.dumps({"outcome": {"status": "operational_failure"}}), encoding="utf-8"
    )

    async def fake_run_parallel(
        args: argparse.Namespace, received_jobs: tuple[Job, ...], logs: Path, *, worker_module: str
    ) -> list[dict[str, object]]:
        assert args is arguments

        # Complete case is skipped.
        # Failed case is the only case scheduled again.
        assert received_jobs == (jobs[1],)

        return [{"index": 2, "case_id": "failed-case", "status": "completed"}]

    monkeypatch.setattr(run_many_module, "_run_parallel", fake_run_parallel)

    exit_code = run_batch(
        args=arguments,
        jobs=jobs,
        worker_module=("graphragprov.experiments.multihop_fidelity.run_one_twowiki"),
    )

    assert exit_code == 0

    summary = json.loads(
        (arguments.artifacts / "_batch" / "summary.json").read_text(encoding="utf-8")
    )

    assert summary["cases"] == [
        {"case_id": "complete-case", "index": 1, "status": "skipped"},
        {"case_id": "failed-case", "index": 2, "status": "completed"},
    ]
