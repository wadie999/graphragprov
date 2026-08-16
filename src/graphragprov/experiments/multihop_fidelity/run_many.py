"""Run many H0 MuSiQue cases concurrently through the trusted run_one CLI."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

from graphragprov.benchmarks.musique import iter_cases
from graphragprov.config import musique_dataset_path
from graphragprov.experiments.multihop_fidelity.config import QueryScope
from graphragprov.providers.deepseek import DEFAULT_DEEPSEEK_MODEL, DEFAULT_DEEPSEEK_TIMEOUT_SECONDS


class Job(NamedTuple):
    ordinal: int
    case_id: str
    support_ids: frozenset[str]


def _say(text: str) -> None:
    print(f"[BATCH] {text}", flush=True)


def _load_jobs(dataset: Path, ids_file: Path) -> tuple[Job, ...]:
    ids = tuple(
        line.strip()
        for line in ids_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )

    if not ids or len(ids) != len(set(ids)):
        raise ValueError("case ID file must be non-empty and contain no duplicates")

    wanted = set(ids)
    supports: dict[str, frozenset[str]] = {}

    for case in iter_cases(dataset):
        if case.case_id in wanted:
            supports[case.case_id] = frozenset(
                paragraph.unit_id for paragraph in case.supporting_paragraphs
            )

    missing = [case_id for case_id in ids if case_id not in supports]

    if missing:
        raise KeyError(f"MuSiQue cases not found: {', '.join(missing)}")

    return tuple(
        Job(index, case_id, supports[case_id]) for index, case_id in enumerate(ids, start=1)
    )


def _command(args: argparse.Namespace, job: Job, reuse: bool) -> list[str]:
    command = [
        sys.executable,
        "-u",
        "-m",
        "graphragprov.experiments.multihop_fidelity.run_one",
        "--case-id",
        job.case_id,
        "--query-scope",
        args.query_scope,
        "--dataset-path",
        str(args.dataset_path),
        "--artifacts",
        str(args.artifacts),
        "--model",
        args.model,
        "--max-tokens",
        str(args.max_tokens),
        "--max-source-attempts",
        str(args.max_source_attempts),
        "--max-query-attempts",
        str(args.max_query_attempts),
        "--llm-timeout-seconds",
        str(args.llm_timeout_seconds),
        "--verbose",
    ]

    if reuse:
        command.append("--reuse-llm-checkpoints")

    return command


async def _run_case(
    args: argparse.Namespace, job: Job, total: int, logs: Path
) -> dict[str, object]:
    result = args.artifacts / job.case_id / args.query_scope / "result.json"

    reuse = bool(args.resume and result.parent.exists())

    log_path = logs / f"{job.ordinal:03d}__{job.case_id}.log"

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    started = time.monotonic()

    _say(f"START {job.ordinal:03d}/{total} case={job.case_id}")

    process = await asyncio.create_subprocess_exec(
        *_command(args, job, reuse),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env,
    )

    try:
        assert process.stdout is not None

        with log_path.open("w", encoding="utf-8") as log:
            while line := await process.stdout.readline():
                text = line.decode(errors="replace")

                log.write(text)
                log.flush()

                print(f"[{job.ordinal:03d}][{job.case_id}] {text}", end="", flush=True)

        exit_code = await process.wait()

    except asyncio.CancelledError:
        process.terminate()
        await process.wait()
        raise

    elapsed = time.monotonic() - started

    status = "completed" if exit_code == 0 and result.is_file() else "failed"

    _say(
        f"DONE  {job.ordinal:03d}/{total} "
        f"case={job.case_id} "
        f"status={status} "
        f"exit={exit_code} "
        f"elapsed={elapsed:.1f}s"
    )

    return {
        "index": job.ordinal,
        "case_id": job.case_id,
        "status": status,
        "exit_code": exit_code,
        "elapsed_seconds": elapsed,
        "result": str(result),
        "log": str(log_path),
    }


async def _run_parallel(
    args: argparse.Namespace, jobs: tuple[Job, ...], logs: Path
) -> list[dict[str, object]]:
    pending = list(jobs)

    active: dict[asyncio.Task[dict[str, object]], Job] = {}

    locked_support_ids: set[str] = set()

    results: list[dict[str, object]] = []

    while pending or active:
        # Start as many non-conflicting cases as possible.
        while len(active) < args.workers:
            candidate = next(
                (
                    index
                    for index, job in enumerate(pending)
                    if locked_support_ids.isdisjoint(job.support_ids)
                ),
                None,
            )

            if candidate is None:
                break

            job = pending.pop(candidate)

            locked_support_ids.update(job.support_ids)

            task = asyncio.create_task(_run_case(args, job, len(jobs), logs))

            active[task] = job

        if not active:
            raise RuntimeError("scheduler deadlocked")

        done, _ = await asyncio.wait(active, return_when=(asyncio.FIRST_COMPLETED))

        for task in done:
            job = active.pop(task)

            locked_support_ids.difference_update(job.support_ids)

            results.append(task.result())

    return results


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=("Run many H0 cases through run_one."))

    parser.add_argument("--case-ids-file", type=Path, required=True)

    parser.add_argument("--workers", type=int, default=4)

    parser.add_argument(
        "--query-scope",
        choices=(QueryScope.SUPPORT.value, QueryScope.REPOSITORY.value),
        default=QueryScope.SUPPORT.value,
    )

    parser.add_argument("--dataset-path", type=Path)

    parser.add_argument("--artifacts", type=Path, required=True)

    parser.add_argument("--model", default=DEFAULT_DEEPSEEK_MODEL)

    parser.add_argument("--max-tokens", type=int, default=16_384)

    parser.add_argument("--max-source-attempts", type=int, default=3)

    parser.add_argument("--max-query-attempts", type=int, default=5)

    parser.add_argument(
        "--llm-timeout-seconds", type=float, default=(DEFAULT_DEEPSEEK_TIMEOUT_SECONDS)
    )

    parser.add_argument("--resume", action="store_true")

    args = parser.parse_args(argv)

    if args.workers < 1:
        parser.error("--workers must be >= 1")

    if args.query_scope == QueryScope.REPOSITORY.value and args.workers != 1:
        parser.error("repository scope requires --workers 1 with shared GraphDB")

    args.dataset_path = (args.dataset_path or musique_dataset_path()).expanduser().resolve()

    args.artifacts = args.artifacts.expanduser().resolve()

    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_arguments(argv)

    jobs = _load_jobs(args.dataset_path, args.case_ids_file)

    logs = args.artifacts / "_batch" / "logs"

    logs.mkdir(parents=True, exist_ok=True)

    runnable: list[Job] = []
    results: list[dict[str, object]] = []

    for job in jobs:
        result = args.artifacts / job.case_id / args.query_scope / "result.json"

        if args.resume and result.is_file():
            _say(f"SKIP  {job.ordinal:03d}/{len(jobs)} case={job.case_id} result exists")

            results.append({"index": job.ordinal, "case_id": job.case_id, "status": "skipped"})

        else:
            runnable.append(job)

    _say(
        f"cases={len(jobs)} "
        f"runnable={len(runnable)} "
        f"workers={args.workers} "
        f"scope={args.query_scope}"
    )

    started = time.monotonic()

    try:
        results.extend(asyncio.run(_run_parallel(args, tuple(runnable), logs)))

    except KeyboardInterrupt:
        _say("INTERRUPT: active run_one processes terminated; checkpoints remain")
        return 130

    results.sort(key=lambda item: int(str(item["index"])))

    failed = sum(item["status"] == "failed" for item in results)

    summary = args.artifacts / "_batch" / "summary.json"

    summary.write_text(
        json.dumps(
            {
                "workers": args.workers,
                "query_scope": (args.query_scope),
                "elapsed_seconds": (time.monotonic() - started),
                "cases": results,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    _say(f"COMPLETE cases={len(jobs)} failed={failed} summary={summary}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
